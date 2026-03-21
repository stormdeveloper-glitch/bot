from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def menu_kb(is_admin: bool = False, web_app_url: str = ""):
    from aiogram.types import WebAppInfo
    keyboard = [
        [KeyboardButton(text="🔎 Anime izlash")],
        [KeyboardButton(text="💎 VIP"), KeyboardButton(text="💰 Hisobim")],
        [KeyboardButton(text="➕ Pul kiritish"), KeyboardButton(text="📚 Qo'llanma")],
        [KeyboardButton(text="👥 Referal"), KeyboardButton(text="💸 Pul o'tkazmasi")],
        [KeyboardButton(text="🎁 Cashback"), KeyboardButton(text="💵 Reklama va Homiylik")]
    ]
    if web_app_url:
        # https:// yo'q bo'lsa avtomatik qo'shamiz
        if not web_app_url.startswith("https://"):
            web_app_url = "https://" + web_app_url.lstrip("http://").lstrip("https://")
        keyboard.insert(0, [KeyboardButton(text="🌐 Web App", web_app=WebAppInfo(url=web_app_url))])
    if is_admin:
        keyboard.append([KeyboardButton(text="🗄 Boshqarish")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def panel_kb(is_super_admin: bool = False):
    keyboard = [
        [KeyboardButton(text="*️⃣ Birlamchi sozlamalar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="✉ Xabar Yuborish")],
        [KeyboardButton(text="📬 Post tayyorlash")],
        [KeyboardButton(text="🎥 Animelar sozlash"), KeyboardButton(text="💳 Hamyonlar")],
        [KeyboardButton(text="🔎 Foydalanuvchini boshqarish")],
        [KeyboardButton(text="📢 Kanallar"), KeyboardButton(text="🎛 Tugmalar"), KeyboardButton(text="📃 Matnlar")],
        [KeyboardButton(text="💸 To'lovlarni Tasdiqlash")]
    ]
    
    # Super admin uchun qo'shimcha tugmalar
    if is_super_admin:
        keyboard.append([KeyboardButton(text="📋 Adminlar")])
        keyboard.append([KeyboardButton(text="📋 Jurnallar")])
    
    keyboard.append([KeyboardButton(text="🤖 Bot holati"), KeyboardButton(text="◀️ Orqaga")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Orqaga")]], resize_keyboard=True)

def boshqarish_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🗄 Boshqarish")]], resize_keyboard=True)

def search_type_kb():
    keyboard = [
        [InlineKeyboardButton(text="🏷 Anime nomi orqali", callback_data="searchByName"), InlineKeyboardButton(text="⏱ So'ngi yuklanganlar", callback_data="lastUploads")],
        [InlineKeyboardButton(text="💬 Janr orqali", callback_data="searchByGenre")],
        [InlineKeyboardButton(text="📌 Kod orqali", callback_data="searchByCode"), InlineKeyboardButton(text="👁️ Eng ko'p ko'rilgan", callback_data="topViewers")],
        [InlineKeyboardButton(text="📚 Barcha animelar", callback_data="allAnimes")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def vip_shop_kb(price: int, currency: str):
    keyboard = [
        [InlineKeyboardButton(text=f"30 kun - {price} {currency}", callback_data="shop=30")],
        [InlineKeyboardButton(text=f"60 kun - {price * 2} {currency}", callback_data="shop=60")],
        [InlineKeyboardButton(text=f"90 kun - {price * 3} {currency}", callback_data="shop=90")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def extend_vip_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗓️ Uzaytirish", callback_data="uzaytirish")]])

def download_kb(anime_id: int, likes: int = 0, dislikes: int = 0):
    total_votes = likes + dislikes
    if total_votes > 0:
        rating = round((likes / total_votes) * 5, 1)
        rating_text = f"⭐ {rating}/5  ({total_votes} ovoz)"
    else:
        rating_text = "⭐ Baholash"

    keyboard = [
        [InlineKeyboardButton(text="▶️ Qismlarni ko'rish", callback_data=f"yuklanolish={anime_id}=1")],
        [
            InlineKeyboardButton(text=f"👍 {likes}", callback_data=f"like={anime_id}"),
            InlineKeyboardButton(text=f"👎 {dislikes}", callback_data=f"dislike={anime_id}"),
        ],
        [InlineKeyboardButton(text=rating_text, callback_data=f"rate={anime_id}")],
        [
            InlineKeyboardButton(text="🔁 Ulashish", callback_data=f"share={anime_id}"),
            InlineKeyboardButton(text="❌ Yopish", callback_data="close")
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

EPISODES_PER_PAGE = 24

def episodes_kb(anime_id: int, current_ep: int, total_eps_data: list, page: int = 0):
    all_eps = [int(ep['qism']) for ep in total_eps_data]
    total = len(all_eps)
    total_pages = max(1, (total + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * EPISODES_PER_PAGE
    end = start + EPISODES_PER_PAGE
    page_eps = all_eps[start:end]

    buttons = []
    for q in page_eps:
        if q == current_ep:
            buttons.append(InlineKeyboardButton(text=f"[ {q} ]", callback_data="null"))
        else:
            buttons.append(InlineKeyboardButton(text=str(q), callback_data=f"yuklanolish={anime_id}={q}"))

    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]

    # Sahifalar arasi navigatsiya
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ep_page={anime_id}={page - 1}={current_ep}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="null"))
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ep_page={anime_id}={page + 1}={current_ep}"))
    elif total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="null"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅ Ortga", callback_data=f"loadAnime={anime_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def payment_confirm_kb(payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_approve={payment_id}")],
        [InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"pay_reject={payment_id}")]
    ])

def vip_plans_kb(price: int, currency: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"30 kun — {price} {currency}",     callback_data="vip_buy=30")],
        [InlineKeyboardButton(text=f"60 kun — {price*2} {currency}",   callback_data="vip_buy=60")],
        [InlineKeyboardButton(text=f"90 kun — {price*3} {currency}",   callback_data="vip_buy=90")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="vip_cancel")]
    ])
