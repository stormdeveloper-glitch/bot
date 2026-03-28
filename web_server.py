from collections import deque
from datetime import datetime
import asyncio
import os
import json
import secrets
import random
import time as _time  # Yangi: vaqtni kesh uchun ishlatamiz
import aiosqlite
import aiohttp
from aiohttp import web

from config import (
    DB_PATH, BOT_TOKEN, BOT_USERNAME, 
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    CHANNEL_ID, CHAT_ID  # Yangi: configdan kanal/guruh IDlari
)

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Auth sessions ──
_sessions: dict = {}

# ─── Game sessions ──
_games: dict = {}

# ─── TG Info Cache (10 daqiqa kesh) ──
_tg_info_cache: dict = {}

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
        self.player_cards  = player_cards
        self.cpu_cards     = cpu_cards
        self.player_score  = 0
        self.cpu_score     = 0
        self.round         = 0
        self.total_rounds  = min(len(player_cards), len(cpu_cards))
        self.user          = user
        self.history       = []
        self.finished      = False
        self.winner        = None

    def current_cards(self):
        if self.round >= self.total_rounds:
            return None, None
        return self.player_cards[self.round], self.cpu_cards[self.round]

    def play_round(self, stat_key: str):
        if self.finished: return None
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

WEB_PORT = int(os.getenv("WEB_PORT", 8080))
_media_cache = {}

async def resolve_file_id(file_id: str) -> dict:
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
                    media_type = "video" if any(fp_lower.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]) else "photo"
                    result = {"url": url, "type": media_type}
                    _media_cache[file_id] = result
                    return result
                else:
                    return {"url": None, "type": "photo", "too_big": "too big" in data.get("description", "").lower()}
    except:
        return {"url": None, "type": "photo"}

# ─── Yangi: Kanal va Chat ma'lumotlarini olish ──
async def _fetch_tg_entity(chat_id: str) -> dict:
    now = _time.time()
    cached = _tg_info_cache.get(chat_id)
    if cached and now - cached["updated"] < 600:
        return cached["data"]

    result = {"ok": False, "title": chat_id, "username": "", "description": "", "members": 0, "avatar_url": None, "link": "", "type": "unknown"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat", params={"chat_id": chat_id}) as r:
                chat_data = await r.json()
            if chat_data.get("ok"):
                ch = chat_data["result"]
                username = ch.get("username", "")
                result.update({
                    "ok": True, "title": ch.get("title", chat_id), "username": username,
                    "description": ch.get("description", ""), "type": ch.get("type", "unknown"),
                    "link": f"https://t.me/{username}" if username else "",
                })
                photo = ch.get("photo", {})
                big_fid = photo.get("big_file_id") or photo.get("small_file_id")
                if big_fid:
                    info = await resolve_file_id(big_fid)
                    if info.get("url"): result["avatar_url"] = f"/media/{big_fid}"

                async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", params={"chat_id": chat_id}) as r2:
                    mc = await r2.json()
                if mc.get("ok"): result["members"] = mc["result"]
    except Exception as e:
        print(f"[_fetch_tg_entity] {chat_id}: {e}")

    _tg_info_cache[chat_id] = {"data": result, "updated": now}
    return result

async def api_channel_stats(request):
    data = await _fetch_tg_entity(CHANNEL_ID)
    extra = {}
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM animelar") as c:
                extra["anime_count"] = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM anime_datas") as c:
                extra["ep_count"] = (await c.fetchone())[0]
    except: pass
    return web.json_response({"ok": True, **data, **extra})

async def api_chat_stats(request):
    data = await _fetch_tg_entity(CHAT_ID)
    return web.json_response({"ok": True, **data})

# ─── Mavjud Media Proxy ───
async def media_proxy(request):
    file_id = request.match_info["file_id"]
    if file_id.startswith("http"): raise web.HTTPFound(file_id)
    info = await resolve_file_id(file_id)
    if not info["url"]: raise web.HTTPNotFound()
    try:
        req_headers = {}
        if request.headers.get("Range"): req_headers["Range"] = request.headers.get("Range")
        async with aiohttp.ClientSession() as session:
            async with session.get(info["url"], headers=req_headers) as tg_resp:
                headers = {
                    "Content-Type": tg_resp.headers.get("Content-Type", "application/octet-stream"),
                    "Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600",
                }
                if tg_resp.headers.get("Content-Length"): headers["Content-Length"] = tg_resp.headers.get("Content-Length")
                if tg_resp.headers.get("Content-Range"): headers["Content-Range"] = tg_resp.headers.get("Content-Range")
                response = web.StreamResponse(status=tg_resp.status, headers=headers)
                await response.prepare(request)
                async for chunk in tg_resp.content.iter_chunked(65536): await response.write(chunk)
                await response.write_eof()
                return response
    except Exception as e: raise web.HTTPInternalServerError(reason=str(e))

# ... [Qolgan barcha API funksiyalari: api_animes, api_episodes, api_admins, sse_stream, api_ai_chat va h.k. o'z holicha qoladi] ...

async def anime_media_info(request):
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rams FROM animelar WHERE id=?", (anime_id,)) as c:
            row = await c.fetchone()
    if not row or not row[0]: return web.json_response({"type": "none", "url": None})
    rams = row[0]
    if rams.startswith("http"):
        low = rams.lower()
        media_type = "video" if any(low.endswith(e) for e in [".mp4", ".mov", ".avi", ".mkv", ".webm"]) else "photo"
        return web.json_response({"type": media_type, "url": rams})
    info = await resolve_file_id(rams)
    return web.json_response({"type": info["type"], "url": f"/media/{rams}" if info["url"] else None})

async def api_animes(request):
    try:
        search = request.rel_url.query.get("q", "").strip()
        async with aiosqlite.connect(DB_PATH) as db:
            if search:
                words = search.split()
                conditions = " AND ".join(["LOWER(a.nom) LIKE ?" for _ in words])
                params = [f"%{w.lower()}%" for w in words]
                query = f"SELECT a.id, a.nom, a.janri, a.rams, a.aniType, a.qismi, a.fandub, a.yili, a.davlat, a.qidiruv, COALESCE(a.liklar,0), COALESCE(a.desliklar,0), COUNT(d.data_id) as ep_count FROM animelar a LEFT JOIN anime_datas d ON d.id = a.id WHERE {conditions} GROUP BY a.id ORDER BY a.qidiruv DESC LIMIT 200"
            else:
                params = []
                query = "SELECT a.id, a.nom, a.janri, a.rams, a.aniType, a.qismi, a.fandub, a.yili, a.davlat, a.qidiruv, COALESCE(a.liklar,0), COALESCE(a.desliklar,0), COUNT(d.data_id) as ep_count FROM animelar a LEFT JOIN anime_datas d ON d.id = a.id GROUP BY a.id ORDER BY a.id DESC LIMIT 500"
            async with db.execute(query, params) as cursor: rows = await cursor.fetchall()
        animes = [{"id": r[0], "nom": r[1], "janri": r[2], "rams_url": f"/poster/{r[0]}", "rams_type": "unknown", "aniType": r[4] or "OnGoing", "fandub": r[6], "yili": r[7], "qidiruv": r[9] or 0, "ep_count": r[12] or 0} for r in rows]
        return web.json_response({"animes": animes, "total": len(animes)})
    except Exception as e: return web.json_response({"animes": [], "total": 0, "error": str(e)})

async def api_episode_preview(request):
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT file_id FROM anime_datas WHERE id=? ORDER BY qism ASC LIMIT 1", (anime_id,)) as c:
            row = await c.fetchone()
    if not row: return web.json_response({"error": "topilmadi"}, status=404)
    return web.json_response({"video_url": f"/media/{row[0]}"})

async def api_episodes(request):
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data_id, qism, file_id FROM anime_datas WHERE id=? ORDER BY qism ASC", (anime_id,)) as c:
            rows = await c.fetchall()
    if not rows: return web.json_response({"episodes": [], "total": 0})
    episodes = []
    for r in rows:
        info = await resolve_file_id(r[2])
        episodes.append({"data_id": r[0], "qism": r[1], "video_url": f"/media/{r[2]}" if info.get("url") else None, "too_big": info.get("too_big", False)})
    return web.json_response({"episodes": episodes, "total": len(episodes)})

async def anime_poster(request):
    anime_id = request.match_info["anime_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT rams FROM animelar WHERE id=?", (anime_id,)) as c:
            row = await c.fetchone()
    if not row or not row[0]: raise web.HTTPNotFound()
    rams = row[0]
    if rams.startswith("http"): raise web.HTTPFound(rams)
    info = await resolve_file_id(rams)
    if info["url"]: raise web.HTTPFound(info["url"])
    raise web.HTTPNotFound()

async def index(request):
    html_path = os.path.join(WEBAPP_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f: html = f.read()
    html = html.replace("{{BOT_USERNAME}}", BOT_USERNAME or "").replace("{{GOOGLE_CLIENT_ID}}", GOOGLE_CLIENT_ID or "")
    return web.Response(text=html, content_type="text/html", charset="utf-8")

async def webapp_page(request):
    html_path = os.path.join(WEBAPP_DIR, "webapp.html")
    with open(html_path, "r", encoding="utf-8") as f: html = f.read()
    html = html.replace("{{BOT_USERNAME}}", BOT_USERNAME or "")
    return web.Response(text=html, content_type="text/html", charset="utf-8")

async def api_admins(request):
    from config import ADMIN_IDS, SUPER_ADMIN_ID
    config_ids = set([SUPER_ADMIN_ID] + ADMIN_IDS)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as c: rows = await c.fetchall()
    all_ids = list(config_ids | {r[0] for r in rows})
    admins = []
    async with aiohttp.ClientSession() as session:
        for uid in all_ids:
            if not uid: continue
            try:
                async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={uid}") as r:
                    data = await r.json()
                if not data.get("ok"): continue
                user = data["result"]
                photo_url = None
                async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos?user_id={uid}&limit=1") as r2:
                    ph_data = await r2.json()
                if ph_data.get("ok") and ph_data["result"]["total_count"] > 0:
                    file_id = ph_data["result"]["photos"][0][-1]["file_id"]
                    async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}") as r3:
                        gf_data = await r3.json()
                    if gf_data.get("ok"): photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{gf_data['result']['file_path']}"
                username = user.get("username", "")
                admins.append({"id": uid, "name": (user.get("first_name", "") + " " + user.get("last_name", "")).strip() or f"User {uid}", "username": f"@{username}" if username else f"ID: {uid}", "link": f"https://t.me/{username}" if username else f"tg://user?id={uid}", "photo": photo_url, "is_super": uid == SUPER_ADMIN_ID})
            except: continue
    admins.sort(key=lambda x: (0 if x["is_super"] else 1))
    return web.json_response({"admins": admins})

_event_history = deque(maxlen=50)
_sse_clients: list = []
def _ts(): return datetime.now().strftime("%H:%M")

async def push_event(event_type: str, text: str, color: str = "c"):
    data = {"type": event_type, "text": text, "color": color, "time": _ts()}
    _event_history.append(data)
    dead = []
    for q in _sse_clients:
        try: await q.put(data)
        except: dead.append(q)
    for q in dead:
        try: _sse_clients.remove(q)
        except: pass

async def sse_stream(request):
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Access-Control-Allow-Origin": "*"})
    await resp.prepare(request)
    q = asyncio.Queue()
    _sse_clients.append(q)
    for ev in list(_event_history)[-10:]:
        try: await resp.write(f"data: {json.dumps(ev)}\n\n".encode())
        except: break
    try:
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=25)
                await resp.write(f"data: {json.dumps(ev)}\n\n".encode())
            except asyncio.TimeoutError: await resp.write(b": ping\n\n")
    except: pass
    finally:
        try: _sse_clients.remove(q)
        except: pass
    return resp

async def api_stats(request):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c: u = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM vip_status") as c: v = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM animelar") as c: a = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM anime_datas") as c: e = (await c.fetchone())[0]
    return web.json_response({"users": u, "vip": v, "animes": a, "eps": e})

_ai_limit_data = {}
async def get_ai_reply(user_msg: str):
    from config import OPENAI_API_KEY
    if not OPENAI_API_KEY: return "Hozircha AI kaliti o'rnatilmagan."
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c: users = (await c.fetchone())[0]
            from config import ADMIN_IDS, SUPER_ADMIN_ID
            async with db.execute("SELECT key, value FROM bot_settings") as c: settings = {r[0]: r[1] for r in await c.fetchall()}
            async with db.execute("SELECT key, value FROM bot_texts") as c: texts = {r[0]: r[1] for r in await c.fetchall()}
            keywords = [w for w in user_msg.split() if len(w) >= 3]
            matched_animes = []
            if keywords:
                for kw in keywords[:5]:
                    async with db.execute("SELECT id, nom FROM animelar WHERE nom LIKE ? LIMIT 3", (f'%{kw}%',)) as c:
                        rows = await c.fetchall()
                        for r in rows:
                            if r not in matched_animes: matched_animes.append(r)
        matched_str = ", ".join([f"{r[1]} (ID:{r[0]})" for r in matched_animes[:8]])
        system_prompt = f"Siz 'ANIME UZ' yordamchisisiz. Stats: {users}. VIP: {settings.get('vip_price')}. Topilganlar: {matched_str or 'yoq'}. QOIDALAR: 1. Anime uchun [ANIME_CARD:ID|Nom|RasmURL] ishlating. 2. O'zbekcha qisqa javob bering."
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json={"model": "gpt-3.5-turbo", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}], "max_tokens": 150, "temperature": 0.4}) as r:
                res = await r.json()
        return res["choices"][0]["message"]["content"] if "choices" in res else "AI xatosi."
    except Exception as e: return f"Xatolik: {str(e)}"

async def api_ai_chat(request):
    try:
        body = await request.json()
        msg = (body.get("message") or "").strip()
        if not msg: return web.json_response({"ok": False, "error": "Bo'sh"}, status=400)
        ip = request.remote
        now = _time.time()
        user_ts = [ts for ts in _ai_limit_data.get(ip, []) if now - ts < 86400]
        if len(user_ts) >= 10: return web.json_response({"ok": False, "error": "Limit tugadi!"})
        reply = await get_ai_reply(msg)
        user_ts.append(now)
        _ai_limit_data[ip] = user_ts
        return web.json_response({"ok": True, "reply": reply})
    except Exception as e: return web.json_response({"ok": False, "error": str(e)})

async def api_payments(request):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, amount, status FROM payments ORDER BY id DESC LIMIT 10") as c: rows = await c.fetchall()
    return web.json_response({"payments": [{"user_id": r[0], "amount": r[1], "status": r[2]} for r in rows]})

async def api_report(request):
    try:
        body = await request.json()
        msg = body.get("message", "").strip()
        if not msg: return web.json_response({"ok": False, "error": "Bo'sh"}, status=400)
        from config import SUPER_ADMIN_ID
        text = f"📩 <b>Yangi murojaat</b>\n<b>Tur:</b> {body.get('type')}\n<b>Ism:</b> {body.get('name')}\n<b>Xabar:</b>\n{msg}"
        async with aiohttp.ClientSession() as session:
            await session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": SUPER_ADMIN_ID, "text": text, "parse_mode": "HTML"})
        return web.json_response({"ok": True})
    except Exception as e: return web.json_response({"ok": False, "error": str(e)})

# ─── Auth & Google ───
async def serve_callback(request):
    path = os.path.join(WEBAPP_DIR, "callback.html")
    with open(path, "r", encoding="utf-8") as f: return web.Response(text=f.read(), content_type="text/html")

async def api_auth_google(request):
    try:
        body = await request.json()
        code = body.get("code", "").strip()
        async with aiohttp.ClientSession() as session:
            async with session.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "redirect_uri": GOOGLE_REDIRECT_URI or body.get("redirect_uri", ""), "grant_type": "authorization_code"}) as resp:
                t_data = await resp.json()
            if "error" in t_data: return web.json_response({"ok": False, "error": t_data.get("error")}, status=400)
            async with session.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {t_data.get('access_token')}"}) as resp2:
                u_info = await resp2.json()
        token = _new_token()
        _sessions[token] = {"id": u_info.get("id"), "name": u_info.get("name"), "email": u_info.get("email"), "picture": u_info.get("picture"), "created": datetime.now().isoformat()}
        return web.json_response({"ok": True, "token": token, "user": _sessions[token]})
    except Exception as e: return web.json_response({"ok": False, "error": str(e)}, status=500)

async def api_auth_me(request):
    user = _sessions.get(request.headers.get("Authorization", "").replace("Bearer ", "").strip())
    return web.json_response({"ok": True, "user": user}) if user else web.json_response({"ok": False}, status=401)

async def api_auth_logout(request):
    _sessions.pop(request.headers.get("Authorization", "").replace("Bearer ", "").strip(), None)
    return web.json_response({"ok": True})

# ─── Game Logic ───
async def _random_anime_cards(n=5):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT a.id, a.nom, a.rams, a.janri, a.yili, a.qidiruv, COUNT(d.data_id) FROM animelar a LEFT JOIN anime_datas d ON d.id = a.id GROUP BY a.id ORDER BY RANDOM() LIMIT ?", (n,)) as c: rows = await c.fetchall()
    return [{"id": r[0], "nom": r[1], "poster": f"/poster/{r[0]}", "janri": r[3], "yili": int(r[4]) if str(r[4]).isdigit() else 0, "qidiruv": r[5] or 0, "ep_count": r[6] or 0} for r in rows]

async def api_game_start(request):
    user = _sessions.get(request.headers.get("Authorization", "").replace("Bearer ", "").strip())
    if not user: return web.json_response({"ok": False}, status=401)
    cards = await _random_anime_cards(10)
    if len(cards) < 6: return web.json_response({"ok": False, "error": "Kam kartalar"}, status=400)
    random.shuffle(cards)
    game_id = _new_token()[:16]
    _games[game_id] = GameState(cards[:5], cards[5:10], user)
    return web.json_response({"ok": True, "game_id": game_id, "state": _games[game_id].to_dict()})

async def api_game_state(request):
    game = _games.get(request.match_info["game_id"])
    return web.json_response({"ok": True, "state": game.to_dict()}) if game else web.json_response({"ok": False}, status=404)

async def api_game_move(request):
    game = _games.get(request.match_info["game_id"])
    if not game or game.finished: return web.json_response({"ok": False}, status=400)
    body = await request.json()
    result = game.play_round(body.get("stat"))
    return web.json_response({"ok": True, "round_result": result, "state": game.to_dict()})

# ─── App Setup ───
async def api_channel_webapp(request):
    """Kanal statistikasi — WebApp uchun DB dan real ma'lumot qaytaradi."""
    try:
        from config import MAIN_CHANNEL_USERNAME
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                users = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM animelar") as c:
                animes = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM anime_datas") as c:
                eps = (await c.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM vip_status") as c:
                vip = (await c.fetchone())[0]
            async with db.execute(
                "SELECT nom, qidiruv FROM animelar ORDER BY qidiruv DESC LIMIT 5"
            ) as c:
                top_animes = [{"nom": r[0], "views": r[1] or 0} for r in await c.fetchall()]
            async with db.execute(
                "SELECT nom, sana FROM animelar ORDER BY id DESC LIMIT 5"
            ) as c:
                recent = [{"nom": r[0], "sana": r[1] or ""} for r in await c.fetchall()]
            async with db.execute("SELECT SUM(qidiruv) FROM animelar") as c:
                total_views = (await c.fetchone())[0] or 0

        return web.json_response({
            "ok": True,
            "channel": MAIN_CHANNEL_USERNAME or "animeuz",
            "stats": {
                "users": users,
                "animes": animes,
                "eps": eps,
                "vip": vip,
                "total_views": total_views,
            },
            "top_animes": top_animes,
            "recent": recent,
        })
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

def create_app():
    app = web.Application(client_max_size=1024**3)
    app.router.add_get("/", index)
    app.router.add_get("/webapp", webapp_page)
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
    app.router.add_get("/callback", serve_callback)
    app.router.add_post("/api/auth/google", api_auth_google)
    app.router.add_get("/api/auth/me", api_auth_me)
    app.router.add_post("/api/auth/logout", api_auth_logout)
    app.router.add_post("/api/game/start", api_game_start)
    app.router.add_get("/api/game/{game_id}", api_game_state)
    app.router.add_post("/api/game/{game_id}/move", api_game_move)
    app.router.add_get("/api/channel_webapp", api_channel_webapp)
    # Yangi Route'lar
    app.router.add_get("/api/channel", api_channel_stats)
    app.router.add_get("/api/chat",    api_chat_stats)
    return app

async def start_web_server():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Web server: http://0.0.0.0:{WEB_PORT}")
    return runner