import asyncio
import logging
import json
import os

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN

from utils.hybrid import detect_tool
from utils.tools_registry import TOOLS
from utils.safe import safe_tool_call
from utils.tools.admin import handle as admin_handler

# ===== LOG =====
logging.basicConfig(level=logging.INFO)

# ===== BOT =====
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ===== DB =====
USERS_DB = "bot_data/users.json"
os.makedirs("bot_data", exist_ok=True)


def load_users():
    if not os.path.exists(USERS_DB):
        with open(USERS_DB, "w") as f:
            json.dump([], f)
    with open(USERS_DB) as f:
        return json.load(f)


def save_user(user_id):
    users = load_users()

    if not any(u["id"] == user_id for u in users):
        users.append({"id": user_id, "blocked": False})

        with open(USERS_DB, "w") as f:
            json.dump(users, f, indent=2)


def is_blocked(user_id):
    users = load_users()
    for u in users:
        if u["id"] == user_id:
            return u.get("blocked", False)
    return False


# ===== HANDLER =====
@dp.message()
async def main_handler(message: types.Message):
    try:
        if not message.text:
            return

        user_id = message.from_user.id

        # 🚫 block check
        if is_blocked(user_id):
            return await message.answer("🚫 Siz bloklangansiz")

        # 💾 save user
        save_user(user_id)

        text = message.text.strip()

        # 🔐 ADMIN
        if text.startswith("/admin"):
            return await admin_handler(message)

        # 🧠 TOOL DETECT
        tool = detect_tool(text)

        if not tool:
            return await message.answer("❌ Tushunmadim")

        if tool in TOOLS:
            await safe_tool_call(TOOLS[tool], message)
        else:
            await message.answer("❌ Tool topilmadi")

    except Exception as e:
        logging.error(f"ERROR: {e}")
        await message.answer("❌ Xatolik yuz berdi")


# ===== STARTUP =====
async def main():
    print("🚀 Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())