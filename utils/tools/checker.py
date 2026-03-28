import requests


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def check_username(username):
    username = username.replace("@", "").strip()

    if not username:
        return "invalid"

    url = f"https://t.me/{username}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=5)

        if res.status_code == 200:
            # sahifa bor → band
            if "tgme_page_title" in res.text:
                return "taken"
        return "free"

    except:
        return "error"


def handle(bot, data):
    # 🤖 BOT MODE
    if bot:
        chat_id = data.chat.id
        text = data.text.strip()

        if not text.startswith("@"):
            bot.send_message(chat_id, "❌ Username yubor (@ bilan)")
            return

        bot.send_message(chat_id, "🔎 Tekshirilmoqda...")

        status = check_username(text)

        if status == "taken":
            bot.send_message(chat_id, f"❌ {text} band")
        elif status == "free":
            bot.send_message(chat_id, f"✅ {text} bo‘sh")
        elif status == "invalid":
            bot.send_message(chat_id, "⚠️ Noto‘g‘ri username")
        else:
            bot.send_message(chat_id, "❌ Xatolik")

    # 🌐 WEB MODE
    else:
        username = data.get("username", "")

        if not username:
            return {"error": "username required"}

        status = check_username(username)

        return {
            "username": username,
            "status": status
        }