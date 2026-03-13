import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", 0))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
MAIN_CHANNEL_ID = os.getenv("MAIN_CHANNEL_ID") # e.g., -1001234567890
MAIN_CHANNEL_USERNAME = os.getenv("MAIN_CHANNEL_USERNAME", "") # e.g., @anime_movie_uz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Railway Volume uchun yo'lni tekshirish
if os.path.exists("/app/data"):
    DATA_DIR = "/app/data"
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")

DB_PATH = os.path.join(DATA_DIR, "bot.db")

# Papkani yaratish (agar yo'q bo'lsa)
os.makedirs(DATA_DIR, exist_ok=True)
