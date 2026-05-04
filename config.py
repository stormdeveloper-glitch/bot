import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", 0))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
MAIN_CHANNEL_ID = os.getenv("MAIN_CHANNEL_ID")
MAIN_CHANNEL_USERNAME = os.getenv("MAIN_CHANNEL_USERNAME", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

# --- ANILIST API ---
ANILIST_CLIENT_ID = os.environ.get("ANILIST_CLIENT_ID")
ANILIST_CLIENT_SECRET = os.environ.get("ANILIST_CLIENT_SECRET")
ANILIST_REDIRECT_URI = os.environ.get("ANILIST_REDIRECT_URI")

# ── Support Bot ───────────────────────────────────────────────────────────────
SUPPORT_BOT_TOKEN   = os.getenv("SUPPORT_BOT_TOKEN", "")       # Support botning tokeni
SUPPORT_GROUP_ID    = int(os.getenv("SUPPORT_GROUP_ID", 0))    # Admin guruhi ID (-100...)
SUPPORT_BOT_USERNAME = os.getenv("SUPPORT_BOT_USERNAME", "")   # @support_bot_username
MAIN_BOT_USERNAME   = os.getenv("BOT_USERNAME", "")            # Asosiy bot username (info uchun)

# Google OAuth
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "")  # https://yoursite.railway.app/callback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Railway Volume uchun yo'lni tekshirish
if os.path.exists("/app/data"):
    DATA_DIR = "/app/data"
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")

DB_PATH = os.path.join(DATA_DIR, "bot.db")

# Papkani yaratish (agar yo'q bo'lsa)
os.makedirs(DATA_DIR, exist_ok=True)
