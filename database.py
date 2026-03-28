import aiosqlite
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                status TEXT DEFAULT 'Oddiy',
                pul INTEGER DEFAULT 0,
                pul2 INTEGER DEFAULT 0,
                odam INTEGER DEFAULT 0,
                ban TEXT DEFAULT 'unban',
                refid INTEGER DEFAULT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS animelar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                rams TEXT NOT NULL,
                qismi TEXT NOT NULL,
                davlat TEXT NOT NULL,
                tili TEXT NOT NULL,
                yili TEXT NOT NULL,
                janri TEXT NOT NULL,
                qidiruv INTEGER DEFAULT 0,
                sana TEXT NOT NULL,
                aniType TEXT DEFAULT '',
                fandub TEXT DEFAULT '',
                kanal TEXT DEFAULT '',
                liklar INTEGER DEFAULT 0,
                desliklar INTEGER DEFAULT 0
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS anime_datas (
                data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                qism INTEGER NOT NULL,
                sana TEXT,
                msg_id INTEGER DEFAULT NULL,
                chat_id INTEGER DEFAULT NULL
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channelId TEXT NOT NULL,
                channelType TEXT NOT NULL,
                channelLink TEXT NOT NULL,
                channelName TEXT DEFAULT ''
            );
        """)
        # Eski DB da channelName ustuni bo'lmasa qo'shamiz
        try:
            await db.execute("ALTER TABLE channels ADD COLUMN channelName TEXT DEFAULT ''")
        except Exception:
            pass  # Ustun allaqachon bor

        # Eski DB da kanal ustuni bo'lmasa qo'shamiz
        try:
            await db.execute("ALTER TABLE animelar ADD COLUMN kanal TEXT DEFAULT ''")
        except Exception:
            pass  # Ustun allaqachon bor

        # anime_datas ga msg_id va chat_id ustunlari
        try:
            await db.execute("ALTER TABLE anime_datas ADD COLUMN msg_id INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE anime_datas ADD COLUMN chat_id INTEGER DEFAULT NULL")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS vip_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                kun INTEGER NOT NULL,
                date TEXT NOT NULL
            );

        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_texts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Default matnlarni kiritish (faqat mavjud bo'lmasa)
        await db.execute("INSERT OR IGNORE INTO bot_texts (key, value) VALUES ('guide', '📚 Foydalanish qo''llanmasi...')")
        await db.execute("INSERT OR IGNORE INTO bot_texts (key, value) VALUES ('ads', '💵 Reklama va Homiylik...')")
        await db.execute("INSERT OR IGNORE INTO bot_texts (key, value) VALUES ('wallet', 'Karta: 8600...')")
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                url TEXT NOT NULL
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                purpose TEXT DEFAULT 'balance',
                status TEXT DEFAULT 'pending',
                check_file_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Default sozlamalar
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('vip_price', '5000')")
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('vip_currency', 'so''m')")
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('referral_bonus', '500')")
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('cashback_percent', '5')")
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('bot_maintenance', '0')")
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('web_app_url', '')")
        await db.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('content_restriction', '0')")
        
        await db.commit()

async def get_db():
    return await aiosqlite.connect(DB_PATH)
