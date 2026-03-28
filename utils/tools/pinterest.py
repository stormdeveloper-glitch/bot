import requests
from bs4 import BeautifulSoup
from config import PINTEREST_API_KEY


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}


def extract_images(html, limit=15):
    soup = BeautifulSoup(html, "html.parser")
    images = []

    for img in soup.find_all("img"):
        src = img.get("src")

        if not src:
            continue

        # kichik rasmlarni tashlab yuboramiz
        if any(x in src for x in ["60x60", "75x75", "236x"]):
            continue

        # sifatli variant
        if "originals" in src or "736x" in src:
            images.append(src)

    # fallback (agar yuqoridagilar topilmasa)
    if not images:
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                images.append(src)

    # unique + limit
    return list(dict.fromkeys(images))[:limit]


def search_pinterest(query, limit=10):
    url = f"https://www.pinterest.com/search/pins/?q={query}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            return []

        return extract_images(res.text, limit)

    except:
        return []


def handle(bot, data):
    # 🤖 BOT MODE
    if bot:
        chat_id = data.chat.id
        query = data.text.strip()

        if not query:
            bot.send_message(chat_id, "❌ So‘rov yuborilmadi")
            return

        bot.send_message(chat_id, "🔍 Qidirilyapti...")

        images = search_pinterest(query, limit=8)

        if not images:
            bot.send_message(chat_id, "❌ Hech narsa topilmadi")
            return

        sent = 0
        for img in images:
            try:
                bot.send_photo(chat_id, img)
                sent += 1
            except:
                continue

        if sent == 0:
            bot.send_message(chat_id, "❌ Rasm yuborib bo‘lmadi")

    # 🌐 WEB MODE
    else:
        query = data.get("query", "").strip()

        if not query:
            return {"error": "query required"}

        images = search_pinterest(query, limit=12)

        return {
            "query": query,
            "count": len(images),
            "results": images
        }