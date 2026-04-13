from collections import deque
from datetime import datetime
import asyncio
import os
import json
import secrets
import random
import aiosqlite
import aiohttp
from aiohttp import web

from config import (
    DB_PATH, BOT_TOKEN, BOT_USERNAME,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    ANILIST_CLIENT_ID, ANILIST_CLIENT_SECRET, ANILIST_REDIRECT_URI,
)

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Auth sessions: token -> {id, name, email, picture, created} ──
_sessions: dict = {}

# ─── Game sessions: game_id -> GameState ─────────────────────────
_games: dict = {}


def _new_token() -> str:
    return secrets.token_urlsafe(32)


class GameState:
    """Anime Karta Jangi — Player vs CPU."""

    STATS = [
        {"key": "ep_count", "label": "Qismlar soni",   "icon": "🎬"},
        {"key": "qidiruv",  "label": "Ko'rilgan marta", "icon": "👁"},
        {"key": "yili",     "label": "Yili",             "icon": "📅"},
    ]

    def __init__(self, player_cards: list, cpu_cards: list, user: dict):
        self.player_cards  = player_cards   # list of anime dicts
        self.cpu_cards     = cpu_cards
        self.player_score  = 0
        self.cpu_score     = 0
        self.round         = 0
        self.total_rounds  = min(len(player_cards), len(cpu_cards))
        self.user          = user
        self.history       = []             # round results
        self.finished      = False
        self.winner        = None

    def current_cards(self):
        if self.round >= self.total_rounds:
            return None, None
        return self.player_cards[self.round], self.cpu_cards[self.round]

    def play_round(self, stat_key: str):
        if self.finished:
            return None
        pc, cc = self.current_cards()
        if pc is None:
            self.finished = True
            return None

        pv = int(pc.get(stat_key) or 0)
        cv = int(cc.get(stat_key) or 0)

        if pv > cv:
            result = "player"
            self.player_score += 1
        elif cv > pv:
            result = "cpu"
            self.cpu_score += 1
        else:
            result = "draw"

        stat_info = next((s for s in self.STATS if s["key"] == stat_key), {})
        self.history.append({
            "round":       self.round + 1,
            "stat_key":    stat_key,
            "stat_label":  stat_info.get("label", stat_key),
            "stat_icon":   stat_info.get("icon", ""),
            "player_val":  pv,
            "cpu_val":     cv,
            "player_card": pc,
            "cpu_card":    cc,
            "result":      result,
        })
        self.round += 1

        # Check finish
        need = (self.total_rounds // 2) + 1
        if self.player_score >= need:
            self.finished = True
            self.winner = "player"
        elif self.cpu_score >= need:
            self.finished = True
            self.winner = "cpu"
        elif self.round >= self.total_rounds:
            self.finished = True
            self.winner = "player" if self.player_score > self.cpu_score else (
                "cpu" if self.cpu_score > self.player_score else "draw"
            )
        return self.history[-1]

    def to_dict(self):
        pc, cc = self.current_cards()
        return {
            "round":        self.round,
            "total_rounds": self.total_rounds,
            "player_score": self.player_score,
            "cpu_score":    self.cpu_score,
            "player_card":  pc,
            "cpu_card":     cc,
            "stats":        self.STATS,
            "history":      self.history,
            "finished":     self.finished,
            "winner":       self.winner,
            "user":         self.user,
        }
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", 8080)))

# Cache: file_id -> {"url": ..., "type": "photo"|"video"}
_media_cache = {}


async def resolve_file_id(file_id: str) -> dict:
    """file_id dan URL va turini aniqlaydi."""
    if file_id in _media_cache:
        return _media_cache[file_id]

    try:
        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(tg_url) as resp:
                data = await resp.json()
                if data.get("ok"):
                    file_path = data["result"]["file_path"]
                    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    fp_lower = file_path.lower()
                    if any(fp_lower.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]):
                        media_type = "video"
                    elif any(fp_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                        media_type = "photo"
                    elif "video" in file_path.lower() or "animations" in file_path.lower():
                        media_type = "video"
                    else:
                        media_type = "photo"
                    result = {"url": url, "type": media_type}
                    _media_cache[file_id] = result
                    return result
                else:
                    err_desc = data.get("description", "unknown")
                    too_big = "too big" in err_desc.lower()
                    print(f"[getFile] XATO — {err_desc} | file_id={file_id[:30]}...")
                    return {"url": None, "type": "video", "too_big": too_big}
    except Exception as e:
        print(f"[getFile] Exception: {e}")
    return {"url": None, "type": "photo"}


async def media_proxy(request):
    """Stream qilish — rasm yoki video. Range request qo'llab-quvvatlaydi."""
    file_id = request.match_info["file_id"]
    if file_id.startswith("http"):
        raise web.HTTPFound(file_id)

    info = await resolve_file_id(file_id)
    if not info["url"]:
        raise web.HTTPNotFound()

    try:
        # Range headerini Telegram CDN ga uzatamiz (video seek uchun muhim)
        req_headers = {}
        range_header = request.headers.get("Range")
        if range_header:
            req_headers["Range"] = range_header

        async with aiohttp.ClientSession() as session:
            async with session.get(info["url"], headers=req_headers) as tg_resp:
                content_type = tg_resp.headers.get("Content-Type", "application/octet-stream")
                content_length = tg_resp.headers.get("Content-Length")
                content_range = tg_resp.headers.get("Content-Range")

                # 206 Partial Content yoki 200 OK — Telegram javobiga qarab
                status = tg_resp.status

                headers = {
                    "Content-Type": content_type,
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "public, max-age=3600",
                }
                if content_length:
                    headers["Content-Length"] = content_length
                if content_range:
                    headers["Content-Range"] = content_range

                response = web.StreamResponse(status=status, headers=headers)
                await response.prepare(request)
                async for chunk in tg_resp.content.iter_chunked(65536):
                    await response.write(chunk)
                await response.write_eof()
                return response
    except Exception as e:
        raise web.HTTPInternalServerError(reason=str(e))


async def anime_media_info(request):
    """
    /api/media/{anime_id} — animening rams turini qaytaradi:
    { "type": "photo"|"video", "url": "/media/{file_id}" }
    """
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rams FROM animelar WHERE id=?", (anime_id,)) as c:
            row = await c.fetchone()

    if not row or not row[0]:
        return web.json_response({"type": "none", "url": None})

    rams = row[0]

    # URL bo'lsa — turini extension dan aniqlaymiz
    if rams.startswith("http"):
        low = rams.lower()
        if any(low.endswith(e) for e in [".mp4", ".mov", ".avi", ".mkv", ".webm"]):
            return web.json_response({"type": "video", "url": rams})
        return web.json_response({"type": "photo", "url": rams})

    # file_id — Telegram dan aniqlaymiz
    info = await resolve_file_id(rams)
    return web.json_response({
        "type": info["type"],
        "url": f"/media/{rams}" if info["url"] else None
    })


async def api_animes(request):
    try:
        search = request.rel_url.query.get("q", "").strip()
        async with aiosqlite.connect(DB_PATH) as db:
            if search:
                words = search.split()
                conditions = " AND ".join(["LOWER(a.nom) LIKE ?" for _ in words])
                params = [f"%{w.lower()}%" for w in words]
                query = f"""
                    SELECT a.id, a.nom, a.janri, a.rams, a.aniType, a.qismi,
                           a.fandub, a.yili, a.davlat, a.qidiruv,
                           COALESCE(a.liklar,0), COALESCE(a.desliklar,0),
                           COUNT(d.data_id) as ep_count, a.yosh_toifa
                    FROM animelar a
                    LEFT JOIN anime_datas d ON d.id = a.id
                    WHERE {conditions}
                    GROUP BY a.id ORDER BY a.qidiruv DESC LIMIT 200
                """
            else:
                params = []
                query = """
                    SELECT a.id, a.nom, a.janri, a.rams, a.aniType, a.qismi,
                           a.fandub, a.yili, a.davlat, a.qidiruv,
                           COALESCE(a.liklar,0), COALESCE(a.desliklar,0),
                           COUNT(d.data_id) as ep_count, a.yosh_toifa
                    FROM animelar a
                    LEFT JOIN anime_datas d ON d.id = a.id
                    GROUP BY a.id ORDER BY a.id DESC LIMIT 500
                """
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        animes = []
        for row in rows:
            rams = row[3] or ""
            animes.append({
                "id":        row[0],
                "nom":       row[1],
                "janri":     row[2],
                "rams_url":  f"/poster/{row[0]}",
                "rams_type": "unknown",
                "rams_id":   rams if not rams.startswith("http") else None,
                "aniType":   row[4] or "OnGoing",
                "fandub":    row[6],
                "yili":      row[7],
                "davlat":    row[8],
                "qidiruv":   row[9] or 0,
                "liklar":    row[10] or 0,
                "ep_count":  row[12] or 0,
                "yosh_toifa": row[13] or "Barcha yoshlar",
            })
        return web.json_response({"animes": animes, "total": len(animes)})
    except Exception as e:
        import traceback; traceback.print_exc()
        return web.json_response({"animes": [], "total": 0, "error": str(e)}, status=200)

async def api_episode_preview(request):
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT file_id FROM anime_datas WHERE id=? ORDER BY qism ASC LIMIT 1",
            (anime_id,)
        ) as c:
            row = await c.fetchone()
    if not row:
        return web.json_response({"error": "topilmadi"}, status=404)
    return web.json_response({"video_url": f"/media/{row[0]}"})


async def api_episodes(request):
    """Anime barcha qismlari ro'yxatini qaytaradi."""
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT data_id, qism, file_id FROM anime_datas WHERE id=? ORDER BY qism ASC",
            (anime_id,)
        ) as c:
            rows = await c.fetchall()
    if not rows:
        return web.json_response({"episodes": [], "total": 0})

    episodes = []
    for r in rows:
        info = await resolve_file_id(r[2])
        episodes.append({
            "data_id": r[0],
            "qism": r[1],
            "video_url": f"/media/{r[2]}" if info.get("url") else None,
            "too_big": info.get("too_big", False),
        })
    return web.json_response({"episodes": episodes, "total": len(episodes)})


async def anime_poster(request):
    """Anime posterini qaytaradi — file_id yoki URL."""
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rams FROM animelar WHERE id=?", (anime_id,)) as c:
            row = await c.fetchone()
    if not row or not row[0]:
        raise web.HTTPNotFound()
    rams = row[0]
    if rams.startswith("http"):
        raise web.HTTPFound(rams)
    info = await resolve_file_id(rams)
    if info["url"]:
        raise web.HTTPFound(info["url"])
    raise web.HTTPNotFound()


async def index(request):
    html_path = os.path.join(WEBAPP_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    # Dinamik qiymatlarni inject qilamiz
    html = html.replace("{{BOT_USERNAME}}", BOT_USERNAME or "")
    html = html.replace("{{GOOGLE_CLIENT_ID}}", GOOGLE_CLIENT_ID or "")
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def api_admins(request):
    """Adminlar ro'yxatini Telegram API dan oladi — config + DB admins jadvali."""
    from config import ADMIN_IDS, SUPER_ADMIN_ID

    # Config dan
    config_ids = set([SUPER_ADMIN_ID] + ADMIN_IDS)

    # DB dagi qo'shilgan adminlar
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as c:
            rows = await c.fetchall()
    db_ids = {r[0] for r in rows}

    # Hammasini birlashtirish
    all_ids = list(config_ids | db_ids)
    all_ids = [uid for uid in all_ids if uid]

    admins = []
    async with aiohttp.ClientSession() as session:
        for uid in all_ids:
            if not uid: continue
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={uid}"
                async with session.get(url) as r:
                    data = await r.json()
                if not data.get("ok"): continue
                user = data["result"]

                photo_url = None
                ph_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos?user_id={uid}&limit=1"
                async with session.get(ph_url) as r2:
                    ph_data = await r2.json()
                if ph_data.get("ok") and ph_data["result"]["total_count"] > 0:
                    file_id = ph_data["result"]["photos"][0][-1]["file_id"]
                    gf_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                    async with session.get(gf_url) as r3:
                        gf_data = await r3.json()
                    if gf_data.get("ok"):
                        fp = gf_data["result"]["file_path"]
                        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}"

                username = user.get("username", "")
                link = f"https://t.me/{username}" if username else f"tg://user?id={uid}"
                fname = user.get("first_name", "")
                lname = user.get("last_name", "")
                full_name = (fname + " " + lname).strip()

                admins.append({
                    "id": uid,
                    "name": full_name or f"User {uid}",
                    "username": f"@{username}" if username else f"ID: {uid}",
                    "link": link,
                    "photo": photo_url,
                    "is_super": uid == SUPER_ADMIN_ID,
                })
            except Exception:
                continue

    admins.sort(key=lambda x: (0 if x["is_super"] else 1))
    return web.json_response({"admins": admins})


import asyncio
import json
from collections import deque
from datetime import datetime

# ─── SSE Event Bus ────────────────────────────────────────────────────────────
# Oxirgi 50 ta hodisani saqlaymiz
_event_history = deque(maxlen=50)
# Barcha ulanib turgan SSE clientlar
_sse_clients: list = []


def _ts():
    return datetime.now().strftime("%H:%M")


async def push_event(event_type: str, text: str, color: str = "c"):
    """
    Barcha SSE clientlarga hodisa yuboradi.
    color: c=cyan, p=pink, g=gold, gr=green
    """
    data = {"type": event_type, "text": text, "color": color, "time": _ts()}
    _event_history.append(data)
    dead = []
    for q in _sse_clients:
        try:
            await q.put(data)
        except Exception:
            dead.append(q)
    for q in dead:
        try:
            _sse_clients.remove(q)
        except ValueError:
            pass


async def sse_stream(request):
    """SSE endpoint — browser shu yerga ulanadi."""
    resp = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    })
    await resp.prepare(request)

    q: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(q)

    # Oxirgi 10 ta tarixiy hodisani darhol yuboramiz
    for ev in list(_event_history)[-10:]:
        msg = f"data: {json.dumps(ev)}\n\n"
        try:
            await resp.write(msg.encode())
        except Exception:
            break

    try:
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=25)
                msg = f"data: {json.dumps(ev)}\n\n"
                await resp.write(msg.encode())
            except asyncio.TimeoutError:
                # Keep-alive ping
                await resp.write(b": ping\n\n")
    except (ConnectionResetError, Exception):
        pass
    finally:
        try:
            _sse_clients.remove(q)
        except ValueError:
            pass
    return resp


async def api_stats(request):
    """Dashboard uchun umumiy statistika."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM vip_status") as c:
            vip = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM animelar") as c:
            animes = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM anime_datas") as c:
            eps = (await c.fetchone())[0]
    return web.json_response({"users": users, "vip": vip, "animes": animes, "eps": eps})


_ai_limit_data = {}  # {ip: [timestamps]}

async def get_ai_reply(user_msg: str):
    """AI mantiqi — ham web, ham bot uchun umumiy."""
    from config import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        return "Hozircha AI kaliti o'rnatilmagan."

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                users = (await c.fetchone())[0]
            
            from config import ADMIN_IDS, SUPER_ADMIN_ID
            admins_info = f"Asosiy admin: {SUPER_ADMIN_ID}. Jami {len(ADMIN_IDS)+1} ta."

            async with db.execute("SELECT key, value FROM bot_settings") as c:
                settings = {r[0]: r[1] for r in await c.fetchall()}
            async with db.execute("SELECT key, value FROM bot_texts") as c:
                texts = {r[0]: r[1] for r in await c.fetchall()}
            
            bot_info = f"VIP narxi: {settings.get('vip_price')} {settings.get('vip_currency')}. Qo'llanma: {texts.get('guide', '')[:100]}..."

            keywords = [w for w in user_msg.split() if len(w) >= 3]
            matched_animes = []
            if keywords:
                for kw in keywords[:5]:
                    async with db.execute("SELECT id, nom, rams FROM animelar WHERE nom LIKE ? LIMIT 3", (f'%{kw}%',)) as c:
                        rows = await c.fetchall()
                        for r in rows:
                            if r not in matched_animes: matched_animes.append(r)

            async with db.execute("SELECT nom FROM animelar ORDER BY qidiruv DESC LIMIT 5") as c:
                top_animes = [r[0] for r in await c.fetchall()]

        matched_str = ", ".join([f"{r[1]} (ID:{r[0]}, Img:/poster/{r[0]})" for r in matched_animes[:8]])
        system_prompt = (
            f"Siz 'ANIME UZ' yordamchisisiz. Stats: {users}. "
            f"Bot: {bot_info}. Adminlar: {admins_info}. "
            f"Topilganlar: {matched_str or 'yoq'}. "
            f"QOIDALAR: 1. Anime uchun FAQAT [ANIME_CARD:ID|Nom|RasmURL] formatini ishlating. "
            f"2. Faqat o'zbek tilida qisqa javob bering."
        )

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "max_tokens": 150, 
            "temperature": 0.4
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json=payload,
                timeout=20
            ) as r:
                res_data = await r.json()

        if "choices" in res_data:
            return res_data["choices"][0]["message"]["content"]
        return "AI xatosi (API)."
    except Exception as e:
        return f"Xatolik: {str(e)}"


async def api_ai_chat(request):
    """Web UI uchun AI chat endpointi."""
    import time
    try:
        body = await request.json()
        user_msg = (body.get("message") or "").strip()
        if not user_msg:
            return web.json_response({"ok": False, "error": "Xabar bo'sh"}, status=400)

        ip = request.remote
        now = time.time()
        user_ts = _ai_limit_data.get(ip, [])
        user_ts = [ts for ts in user_ts if now - ts < 86400]
        
        if len(user_ts) >= 10:
            return web.json_response({"ok": False, "error": "Kunlik limit (10 ta) tugadi!"})

        reply = await get_ai_reply(user_msg)
        user_ts.append(now)
        _ai_limit_data[ip] = user_ts
        return web.json_response({"ok": True, "reply": reply})

    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def api_payments(request):
    """So'nggi 10 ta to'lov."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, amount, status FROM payments ORDER BY id DESC LIMIT 10"
        ) as c:
            rows = await c.fetchall()
    payments = [{"user_id": r[0], "amount": r[1], "status": r[2]} for r in rows]
    return web.json_response({"payments": payments})


async def api_report(request):
    """Saytdan shikoyat / taklif — super adminga Telegram xabar yuboradi."""
    try:
        body = await request.json()
        msg_type  = body.get("type", "other")
        name      = (body.get("name") or "").strip()
        username  = (body.get("username") or "").strip()
        message   = (body.get("message") or "").strip()

        if not message:
            return web.json_response({"ok": False, "error": "Xabar bo'sh"}, status=400)

        type_labels = {
            "bug":        "🐛 Xatolik",
            "suggestion": "💡 Taklif",
            "complaint":  "😤 Shikoyat",
            "other":      "📌 Boshqa",
        }
        type_label = type_labels.get(msg_type, "📌 Boshqa")

        text = (
            f"📩 <b>Yangi murojaat — Sayt</b>\n"
            f"{'─' * 28}\n"
            f"<b>Tur:</b> {type_label}\n"
        )
        if name:
            text += f"<b>Ism:</b> {name}\n"
        if username:
            text += f"<b>Username:</b> {username}\n"
        text += f"\n<b>Xabar:</b>\n{message}"

        from config import SUPER_ADMIN_ID
        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(tg_url, json={
                "chat_id":    SUPER_ADMIN_ID,
                "text":       text,
                "parse_mode": "HTML",
            })

        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


# ═══════════════════════════════════════════════
#  ANILIST INTEGRATION
# ═══════════════════════════════════════════════

# AniList OAuth state → session_token mapping
_anilist_states: dict = {}   # state -> session_token
# AniList access tokens per session
_anilist_tokens: dict = {}   # session_token -> anilist_access_token

ANILIST_GRAPHQL = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      coverImage { large medium }
      status
      averageScore
      episodes
      season
      seasonYear
      genres
      format
    }
  }
}
"""


async def api_anilist_search(request: web.Request) -> web.Response:
    """
    GET /api/anilist/search?q=naruto&page=1&per=20
    AniList GraphQL API orqali global anime qidirish.
    """
    q = request.rel_url.query.get("q", "").strip()
    if not q:
        return web.json_response({"ok": False, "error": "q parametri kerak"}, status=400)

    page = int(request.rel_url.query.get("page", 1))
    per_page = min(int(request.rel_url.query.get("per", 20)), 50)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANILIST_GRAPHQL,
                json={
                    "query": SEARCH_QUERY,
                    "variables": {"search": q, "page": page, "perPage": per_page},
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()

        if "errors" in data:
            errs = "; ".join(e.get("message", "?") for e in data["errors"])
            return web.json_response({"ok": False, "error": errs}, status=502)

        media_list = data.get("data", {}).get("Page", {}).get("media", [])

        results = []
        for m in media_list:
            title = (
                m["title"].get("english")
                or m["title"].get("romaji")
                or m["title"].get("native")
                or "Nomsiz"
            )
            results.append({
                "id":           m["id"],
                "title":        title,
                "title_romaji": m["title"].get("romaji") or "",
                "title_native": m["title"].get("native") or "",
                "cover":        m["coverImage"].get("large") or m["coverImage"].get("medium") or "",
                "status":       m.get("status") or "UNKNOWN",
                "score":        m.get("averageScore"),   # 0-100 or null
                "episodes":     m.get("episodes"),
                "season":       m.get("season") or "",
                "year":         m.get("seasonYear"),
                "genres":       m.get("genres") or [],
                "format":       m.get("format") or "",
            })

        return web.json_response({"ok": True, "results": results, "total": len(results)})

    except asyncio.TimeoutError:
        return web.json_response({"ok": False, "error": "AniList timeout"}, status=504)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def api_auth_anilist(request: web.Request) -> web.Response:
    """
    GET /api/auth/anilist  (Authorization: Bearer <session_token>)
    Foydalanuvchini AniList OAuth sahifasiga yo'naltiradi.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token or token not in _sessions:
        return web.json_response({"ok": False, "error": "Avval Google bilan kiring"}, status=401)

    if not ANILIST_CLIENT_ID or not ANILIST_REDIRECT_URI:
        return web.json_response(
            {"ok": False, "error": "ANILIST_CLIENT_ID yoki ANILIST_REDIRECT_URI sozlanmagan"},
            status=500,
        )

    state = secrets.token_urlsafe(16)
    _anilist_states[state] = token   # state → session_token

    auth_url = (
        f"https://anilist.co/api/v2/oauth/authorize"
        f"?client_id={ANILIST_CLIENT_ID}"
        f"&redirect_uri={ANILIST_REDIRECT_URI}"
        f"&response_type=code"
        f"&state={state}"
    )
    return web.json_response({"ok": True, "url": auth_url})


async def callback_anilist(request: web.Request) -> web.Response:
    """
    GET /callback/anilist?code=...&state=...
    AniList OAuth callback — kodni token bilan almashtirib, sessiyaga yozadi.
    """
    code = request.rel_url.query.get("code", "").strip()
    state = request.rel_url.query.get("state", "").strip()

    if not code or not state:
        return web.Response(
            text="<h2>❌ Xatolik: code yoki state yo'q</h2>",
            content_type="text/html",
            status=400,
        )

    session_token = _anilist_states.pop(state, None)
    if not session_token:
        return web.Response(
            text="<h2>❌ Xatolik: noto'g'ri state. Qayta urinib ko'ring.</h2>",
            content_type="text/html",
            status=400,
        )

    if not ANILIST_CLIENT_ID or not ANILIST_CLIENT_SECRET or not ANILIST_REDIRECT_URI:
        return web.Response(
            text="<h2>❌ AniList sozlamalari to'liq emas</h2>",
            content_type="text/html",
            status=500,
        )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://anilist.co/api/v2/oauth/token",
                json={
                    "grant_type":    "authorization_code",
                    "client_id":     ANILIST_CLIENT_ID,
                    "client_secret": ANILIST_CLIENT_SECRET,
                    "redirect_uri":  ANILIST_REDIRECT_URI,
                    "code":          code,
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                token_data = await resp.json()

        if "error" in token_data:
            err = token_data.get("error_description") or token_data.get("error", "Token xatosi")
            return web.Response(
                text=f"<h2>❌ AniList token xatosi: {err}</h2>",
                content_type="text/html",
                status=400,
            )

        access_token = token_data.get("access_token", "")
        _anilist_tokens[session_token] = access_token

        # Foydalanuvchi ma'lumotini AniList dan olamiz
        viewer_query = "query { Viewer { id name avatar { large } siteUrl } }"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANILIST_GRAPHQL,
                json={"query": viewer_query},
                headers={
                    "Authorization":  f"Bearer {access_token}",
                    "Content-Type":   "application/json",
                    "Accept":         "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                viewer_data = await resp.json()

        viewer = viewer_data.get("data", {}).get("Viewer", {})
        if viewer and session_token in _sessions:
            _sessions[session_token]["anilist"] = {
                "id":       viewer.get("id"),
                "name":     viewer.get("name"),
                "avatar":   (viewer.get("avatar") or {}).get("large") or "",
                "site_url": viewer.get("siteUrl") or "",
            }

        # Muvaffaqiyatli — sahifani yopamiz
        html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AniList ulandi</title>
<style>
  body{margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;
       background:#0a0a18;font-family:sans-serif;color:#cce4ff}
  .box{background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.25);border-radius:16px;
       padding:40px 48px;text-align:center;max-width:380px}
  .ico{font-size:3rem;margin-bottom:16px}
  h2{color:#00d4ff;font-size:1.2rem;margin:0 0 10px}
  p{font-size:.85rem;color:#7aadcc;margin:0 0 22px}
  button{background:linear-gradient(90deg,#00d4ff,#8b5cf6);border:none;color:#fff;
         padding:10px 28px;border-radius:20px;cursor:pointer;font-weight:700;font-size:.85rem}
</style></head>
<body>
  <div class="box">
    <div class="ico">✅</div>
    <h2>AniList ulandi!</h2>
    <p>Hisobingiz muvaffaqiyatli bog'landi. Bu oynani yopishingiz mumkin.</p>
    <button onclick="window.close()">Oynani yopish</button>
  </div>
  <script>setTimeout(()=>window.close(),3000)</script>
</body></html>"""
        return web.Response(text=html, content_type="text/html")

    except asyncio.TimeoutError:
        return web.Response(
            text="<h2>❌ AniList serveri javob bermadi (timeout)</h2>",
            content_type="text/html",
            status=504,
        )
    except Exception as e:
        return web.Response(
            text=f"<h2>❌ Xatolik: {e}</h2>",
            content_type="text/html",
            status=500,
        )


async def api_anilist_status(request: web.Request) -> web.Response:
    """
    GET /api/auth/anilist/status  (Authorization: Bearer <session_token>)
    AniList ulanish holatini qaytaradi.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    user = _sessions.get(token)
    if not user:
        return web.json_response({"ok": False, "error": "Autentifikatsiya talab etiladi"}, status=401)

    anilist_info = user.get("anilist")
    connected = bool(_anilist_tokens.get(token)) and bool(anilist_info)
    return web.json_response({
        "ok":        True,
        "connected": connected,
        "anilist":   anilist_info if connected else None,
    })


# ═══════════════════════════════════════════════
#  GOOGLE OAUTH
# ═══════════════════════════════════════════════

async def serve_callback(request):
    """callback.html ni qaytaradi."""
    path = os.path.join(WEBAPP_DIR, "callback.html")
    with open(path, "r", encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html", charset="utf-8")


async def api_auth_google(request):
    """
    POST /api/auth/google  { code: "..." }
    Google authorization code ni token bilan almashtirib,
    user ma'lumotlarini qaytaradi va session yaratadi.
    """
    try:
        body = await request.json()
        code = body.get("code", "").strip()
        if not code:
            return web.json_response({"ok": False, "error": "code yo'q"}, status=400)

        redirect_uri = GOOGLE_REDIRECT_URI or body.get("redirect_uri", "")
        if not redirect_uri:
            return web.json_response({"ok": False, "error": "GOOGLE_REDIRECT_URI sozlanmagan"}, status=500)

        async with aiohttp.ClientSession() as session:
            # 1. Code → access token
            async with session.post("https://oauth2.googleapis.com/token", data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            }) as resp:
                token_data = await resp.json()

            if "error" in token_data:
                return web.json_response({"ok": False, "error": token_data.get("error_description", token_data["error"])}, status=400)

            access_token = token_data.get("access_token")

            # 2. Access token → user info
            async with session.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as resp:
                user_info = await resp.json()

        # 3. Session yaratish
        session_token = _new_token()
        _sessions[session_token] = {
            "id":      user_info.get("id", ""),
            "name":    user_info.get("name", "Foydalanuvchi"),
            "email":   user_info.get("email", ""),
            "picture": user_info.get("picture", ""),
            "created": datetime.now().isoformat(),
        }

        return web.json_response({
            "ok":    True,
            "token": session_token,
            "user":  _sessions[session_token],
        })

    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def api_auth_me(request):
    """GET /api/auth/me — token orqali user ma'lumotlarini olish."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    user = _sessions.get(token)
    if not user:
        return web.json_response({"ok": False, "error": "Autentifikatsiya talab etiladi"}, status=401)
    return web.json_response({"ok": True, "user": user})


async def api_auth_logout(request):
    """POST /api/auth/logout — session o'chirish."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    _sessions.pop(token, None)
    return web.json_response({"ok": True})


# ═══════════════════════════════════════════════
#  ANIME KARTA JANGI
# ═══════════════════════════════════════════════

async def _random_anime_cards(n: int = 5) -> list:
    """DB dan tasodifiy n ta anime kartani oladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.id, a.nom, a.rams, a.janri, a.yili, a.aniType, a.fandub,
                   COALESCE(a.qidiruv,0) as qidiruv,
                   COUNT(d.data_id) as ep_count
            FROM animelar a
            LEFT JOIN anime_datas d ON d.id = a.id
            GROUP BY a.id
            ORDER BY RANDOM() LIMIT ?
        """, (n,)) as c:
            rows = await c.fetchall()

    cards = []
    for r in rows:
        rams = r[2] or ""
        poster = f"/poster/{r[0]}" if rams else ""
        cards.append({
            "id":       r[0],
            "nom":      r[1] or "Nomsiz",
            "poster":   poster,
            "janri":    r[3] or "—",
            "yili":     int(r[4]) if r[4] and str(r[4]).isdigit() else 0,
            "aniType":  r[5] or "—",
            "fandub":   r[6] or "—",
            "qidiruv":  int(r[7]) if r[7] else 0,
            "ep_count": int(r[8]) if r[8] else 0,
        })
    return cards


async def api_game_start(request):
    """POST /api/game/start — yangi o'yin boshlash."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    user = _sessions.get(token)
    if not user:
        return web.json_response({"ok": False, "error": "Login talab etiladi"}, status=401)

    try:
        cards = await _random_anime_cards(10)
        if len(cards) < 6:
            return web.json_response({"ok": False, "error": "DB da yetarli anime yo'q"}, status=400)

        random.shuffle(cards)
        n = len(cards) // 2
        player_cards = cards[:n]
        cpu_cards    = cards[n:n*2]

        game_id = _new_token()[:16]
        _games[game_id] = GameState(player_cards, cpu_cards, user)

        return web.json_response({
            "ok":      True,
            "game_id": game_id,
            "state":   _games[game_id].to_dict(),
        })
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def api_game_state(request):
    """GET /api/game/{game_id} — o'yin holatini olish."""
    game_id = request.match_info["game_id"]
    game = _games.get(game_id)
    if not game:
        return web.json_response({"ok": False, "error": "O'yin topilmadi"}, status=404)
    return web.json_response({"ok": True, "state": game.to_dict()})


async def api_game_move(request):
    """POST /api/game/{game_id}/move  { stat: "ep_count"|"qidiruv"|"yili" }"""
    game_id = request.match_info["game_id"]
    game = _games.get(game_id)
    if not game:
        return web.json_response({"ok": False, "error": "O'yin topilmadi"}, status=404)
    if game.finished:
        return web.json_response({"ok": False, "error": "O'yin tugagan"}, status=400)

    body = await request.json()
    stat = body.get("stat", "")
    valid = [s["key"] for s in GameState.STATS]
    if stat not in valid:
        return web.json_response({"ok": False, "error": f"Noto'g'ri stat. Mumkin: {valid}"}, status=400)

    result = game.play_round(stat)
    return web.json_response({"ok": True, "round_result": result, "state": game.to_dict()})


def create_app():
    app = web.Application(client_max_size=1024**3)
    app.router.add_get("/", index)
    app.router.add_get("/api/animes", api_animes)
    app.router.add_get("/poster/{anime_id}", anime_poster)
    app.router.add_get("/api/admins", api_admins)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/events", sse_stream)
    app.router.add_get("/api/payments", api_payments)
    app.router.add_get("/api/media/{anime_id}", anime_media_info)
    app.router.add_get("/api/preview/{anime_id}", api_episode_preview)
    app.router.add_get("/api/episodes/{anime_id}", api_episodes)
    app.router.add_get("/media/{file_id}", media_proxy)
    app.router.add_post("/api/ai/chat", api_ai_chat)
    app.router.add_post("/api/report",  api_report)
    # OAuth — Google
    app.router.add_get( "/callback",         serve_callback)
    app.router.add_post("/api/auth/google",  api_auth_google)
    app.router.add_get( "/api/auth/me",      api_auth_me)
    app.router.add_post("/api/auth/logout",  api_auth_logout)
    # OAuth — AniList
    app.router.add_get( "/api/auth/anilist",         api_auth_anilist)
    app.router.add_get( "/api/auth/anilist/status",  api_anilist_status)
    app.router.add_get( "/callback/anilist",         callback_anilist)
    # AniList search
    app.router.add_get( "/api/anilist/search",       api_anilist_search)
    # Game
    app.router.add_post("/api/game/start",          api_game_start)
    app.router.add_get( "/api/game/{game_id}",       api_game_state)
    app.router.add_post("/api/game/{game_id}/move",  api_game_move)
    return app


async def start_web_server():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Web server: http://0.0.0.0:{WEB_PORT}")
    return runner
