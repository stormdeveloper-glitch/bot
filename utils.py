import aiosqlite
from config import ADMIN_IDS, SUPER_ADMIN_ID, DB_PATH
from aiogram import Bot

async def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS or user_id == SUPER_ADMIN_ID:
        return True
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,)) as cursor:
            admin = await cursor.fetchone()
            return admin is not None

async def is_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

async def check_subscription(user_id: int, bot: Bot) -> bool:
    # Logic to check subscription (social kanallar tekshirilmaydi — ular Telegram emas)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM channels WHERE channelType IN ('public', 'request')") as cursor:
            channels = await cursor.fetchall()
            
    if not channels:
        return True
        
    for channel in channels:
        channel_id = channel[1] # channelId
        channel_type = channel[2] # channelType
        channel_link = channel[3] # channelLink
        
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception as e:
            # If bot is not admin in channel or can't check
            print(f"Error checking subscription for {channel_id}: {e}")
            return False
            
    return True

async def get_subscription_keyboard(user_id: int, bot: Bot):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Barcha majburiy kanallar (social ham ko'rsatiladi, lekin tekshirilmaydi)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM channels WHERE channelType IN ('public', 'request', 'social')") as cursor:
            channels = await cursor.fetchall()
            
    buttons = []
    for channel in channels:
        channel_id = channel[1]
        channel_type = channel[2]
        channel_link = channel[3]

        if channel_type == 'social':
            # Ijtimoiy tarmoqlar — channelId ni nom sifatida ishlatamiz
            title = channel_id  # Admin qo'shganda yozgan nom (masalan: Instagram, YouTube)
            buttons.append([InlineKeyboardButton(text=f"🌐 {title}", url=channel_link)])
        else:
            try:
                chat = await bot.get_chat(channel_id)
                title = chat.title
            except:
                title = "Kanalga o'tish"
            buttons.append([InlineKeyboardButton(text=f"📢 {title}", url=channel_link)])
        
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
