def normalize_username(text):
    text = text.strip()

    if "t.me/" in text:
        return text.split("t.me/")[-1].strip()

    return text.replace("@", "").strip()


def get_channel_info(bot, username):
    try:
        chat = bot.get_chat(f"@{username}")

        return {
            "title": chat.title,
            "username": username,
            "type": chat.type,
            "members": getattr(chat, "members_count", None)
        }

    except:
        return None


def handle(bot, data):
    # 🤖 BOT MODE
    if bot:
        chat_id = data.chat.id
        text = data.text.strip()

        username = normalize_username(text)

        if not username:
            bot.send_message(chat_id, "❌ Username yubor (@ yoki link)")
            return

        bot.send_message(chat_id, "📊 Tekshirilmoqda...")

        info = get_channel_info(bot, username)

        if not info:
            bot.send_message(chat_id, "❌ Kanal topilmadi yoki private")
            return

        msg = (
            f"📢 {info['title']}\n"
            f"👤 @{info['username']}\n"
            f"📦 Turi: {info['type']}\n"
            f"👥 Obunachilar: {info['members'] if info['members'] else 'Nomaʼlum'}"
        )

        bot.send_message(chat_id, msg)

    # 🌐 WEB MODE
    else:
        return {"error": "bot only"}