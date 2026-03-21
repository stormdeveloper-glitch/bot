import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import init_db
from handlers import user_handlers, admin_handlers, inline_handlers
from web_server import start_web_server

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)
    dp.include_router(inline_handlers.router)

    # Web server ham bir vaqtda ishlasin
    web_runner = await start_web_server()

    print("Bot ishga tushdi...")
    try:
        await dp.start_polling(bot)
    finally:
        await web_runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")
