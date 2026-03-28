import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import admin_handlers, user_handlers, inline_handlers

# ===== LOG =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ===== BOT & DISPATCHER =====
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ===== ROUTER ULASH =====
dp.include_router(admin_handlers.router)
dp.include_router(user_handlers.router)
dp.include_router(inline_handlers.router)


# ===== STARTUP =====
async def on_startup():
    logger.info("🗄 Database initsializatsiya...")
    await init_db()
    me = await bot.get_me()
    logger.info(f"🚀 Bot ishga tushdi: @{me.username}")


async def main():
    dp.startup.register(on_startup)

    # Web server bilan birga ishlatish (Railway uchun)
    try:
        from web_server import create_app
        import aiohttp.web as web

        app = create_app()

        PORT = int(os.getenv("PORT", 8080))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"🌐 Web server: http://0.0.0.0:{PORT}")
    except Exception as e:
        logger.warning(f"⚠️ Web server ishlamadi: {e}")

    # Bot polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
