from collections import deque
from datetime import datetime
import asyncio
import os
import json
import aiosqlite
import aiohttp
from aiohttp import web

from config import DB_PATH, BOT_TOKEN, BOT_USERNAME

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_PORT = int(os.getenv("WEB_PORT", 8080))

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
                    # Turini file_path dan aniqlaymiz
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
    except Exception:
        pass
    return {"url": None, "type": "photo"}


async def media_proxy(request):
    """Stream qilish — rasm yoki video."""
    file_id = request.match_info["file_id"]
    if file_id.startswith("http"):
        raise web.HTTPFound(file_id)

    info = await resolve_file_id(file_id)
    if not info["url"]:
        raise web.HTTPNotFound()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(info["url"]) as tg_resp:
                content_type = tg_resp.headers.get("Content-Type", "application/octet-stream")
                content_length = tg_resp.headers.get("Content-Length")
                headers = {
                    "Content-Type": content_type,
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "public, max-age=3600",
                }
                if content_length:
                    headers["Content-Length"] = content_length
                response = web.StreamResponse(status=200, headers=headers)
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
                           COUNT(d.data_id) as ep_count
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
                           COUNT(d.data_id) as ep_count
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
    # BOT_USERNAME — index.html da qattiq muhrlangan, inject shart emas
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

async def api_ai_chat(request):
    """AI Chatbot ChatGPT orqali savollarga javob beradi (Qattiq limitlar bilan)."""
    from config import OPENAI_API_KEY
    import time
    try:
        body = await request.json()
        user_msg = (body.get("message") or "").strip()
        if not user_msg:
            return web.json_response({"ok": False, "error": "Xabar bo'sh"}, status=400)

        # Qattiq Limit: IP bo'yicha 24 soatda (bir kunda) 10 ta xabar
        ip = request.remote
        now = time.time()
        user_ts = _ai_limit_data.get(ip, [])
        user_ts = [ts for ts in user_ts if now - ts < 86400] # 24 soat
        
        if len(user_ts) >= 10:
            return web.json_response({
                "ok": False, 
                "error": "Juda qat'iy limit: Bir kunda faqat 10 ta xabar yuborish mumkin!"
            }, status=200)

        # Uzunlik limiti: 200 belgi
        if len(user_msg) > 200:
            return web.json_response({
                "ok": False, 
                "error": "Xabar juda uzun (maksimal 200 belgi)!"
            }, status=200)

        if not OPENAI_API_KEY:
             return web.json_response({"ok": True, "reply": "Hozircha AI kaliti o'rnatilmagan. Iltimos, Railway panelida OPENAI_API_KEY o'rnatilganini tekshiring."})

        # Kontekstni ixchamlashtirish (token tejash)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c:
                users = (await c.fetchone())[0]
            
            # Adminlar ma'lumotlari
            async with db.execute("SELECT name, username FROM admins LIMIT 5") as c:
                admins = [f"{r[0]} (@{r[1]})" for r in await c.fetchall()]

            # Foydalanuvchi xabaridan anime qidirish (Rasm bilan)
            keywords = [w for w in user_msg.split() if len(w) >= 3]
            matched_animes = []
            if keywords:
                for kw in keywords[:5]:
                    async with db.execute("SELECT id, nom, rams_url FROM animelar WHERE nom LIKE ? LIMIT 3", (f'%{kw}%',)) as c:
                        rows = await c.fetchall()
                        for r in rows:
                            if r not in matched_animes: matched_animes.append(r)

            async with db.execute("SELECT nom FROM animelar ORDER BY qidiruv DESC LIMIT 5") as c:
                top_animes = [r[0] for r in await c.fetchall()]

        matched_str = ", ".join([f"{r[1]} (ID:{r[0]}, Img:{r[2]})" for r in matched_animes[:8]])
        system_prompt = (
            f"Siz 'ANIME UZ' yordamchisisiz. Stats: {users}. "
            f"Adminlar: {', '.join(admins)}. "
            f"Topilgan animelar: {matched_str or 'yoq'}. "
            f"QOIDALAR: 1. Anime tavsiya qilsang FAQAT [ANIME_CARD:ID|Nom|RasmURL] formatini matn oxirida ishlating. "
            f"2. Adminlar haqida so'rashsa, yuqoridagi ro'yxatdan foydalaning. "
            f"3. Faqat o'zbek tilida qisqa javob bering."
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
            user_ts.append(now)
            _ai_limit_data[ip] = user_ts
            reply = res_data["choices"][0]["message"]["content"]
            return web.json_response({"ok": True, "reply": reply})
        else:
            return web.json_response({"ok": False, "error": "API xatosi"})

    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=200)


async def api_payments(request):
    """So'nggi 10 ta to'lov."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, amount, status FROM payments ORDER BY id DESC LIMIT 10"
        ) as c:
            rows = await c.fetchall()
    payments = [{"user_id": r[0], "amount": r[1], "status": r[2]} for r in rows]
    return web.json_response({"payments": payments})


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
    app.router.add_get("/media/{file_id}", media_proxy)
    app.router.add_post("/api/ai/chat", api_ai_chat)
    return app


async def start_web_server():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Web server: http://0.0.0.0:{WEB_PORT}")
    return runner
