import aiosqlite
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, ChatJoinRequest,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

from config import DB_PATH, ADMIN_IDS, SUPER_ADMIN_ID
from keyboards import menu_kb, search_type_kb, download_kb, episodes_kb, payment_confirm_kb, vip_plans_kb
from utils import check_subscription, get_subscription_keyboard, is_admin
from states import UserStates, PaymentStates, VipStates

router = Router()

@router.chat_join_request()
async def auto_approve_join_request(request: ChatJoinRequest, bot: Bot):
    """Foydalanuvchi kanalga qo'shilish so'rovi yuborganda avtomatik tasdiqlaydi."""
    try:
        await request.approve()
        await bot.send_message(
            request.from_user.id,
            "<b>✅ Kanallarga obuna so'rovingiz qabul qilindi!</b>\n\n"
            "Endi botdan to'liq foydalanishingiz mumkin.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"ChatJoinRequest error: {e}")


MAINTENANCE_MSG = (
    "⚠️ <b>Bot tamirlanyapti</b>\n"
    "Baza bilan aloqa yo'q\n\n"
    "<i>Tez orada ishga tushadi, kuting...</i>"
)

async def is_maintenance() -> bool:
    """Texnik ish rejimi yoqilganligini tekshiradi."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT value FROM bot_settings WHERE key='bot_maintenance'"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] == "1" if row else False
    except:
        return False



@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id

    # Admin bo'lmasa texnik ish rejimini tekshir
    if not await is_admin(user_id) and await is_maintenance():
        await message.answer(MAINTENANCE_MSG, parse_mode="HTML")
        return

    if not await check_subscription(user_id, bot):
        keyboard = await get_subscription_keyboard(user_id, bot)
        await message.answer(
            "<b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling❗️</b>",
            reply_markup=keyboard, parse_mode="HTML"
        )
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

    await state.clear()

    # Referal bonus
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id != user_id:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT refid FROM users WHERE user_id=?", (user_id,)) as c:
                    row = await c.fetchone()
                if row and row[0] is None:
                    async with db.execute(
                        "SELECT value FROM bot_settings WHERE key='referral_bonus'"
                    ) as c:
                        bonus_row = await c.fetchone()
                    bonus = int(bonus_row[0]) if bonus_row else 500
                    await db.execute(
                        "UPDATE users SET refid=?, pul2=pul2+? WHERE user_id=?",
                        (ref_id, bonus, user_id)
                    )
                    await db.execute(
                        "UPDATE users SET pul=pul+?, odam=odam+1 WHERE user_id=?",
                        (bonus, ref_id)
                    )
                    await db.commit()
                    try:
                        await bot.send_message(
                            ref_id,
                            f"🎉 Yangi taklif! Foydalanuvchi <code>{user_id}</code> botga qo'shildi.\n"
                            f"💰 Sizga <b>{bonus}</b> so'm bonus qo'shildi!",
                            parse_mode="HTML"
                        )
                    except:
                        pass
        await show_anime(message, int(args[1]))
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM bot_settings WHERE key='web_app_url'"
        ) as c:
            web_row = await c.fetchone()
        web_url = (web_row[0] if web_row else "") or ""

    await message.answer(
        f"✨ Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\nAnime botiga xush kelibsiz!",
        reply_markup=menu_kb(await is_admin(user_id), web_app_url=web_url), parse_mode="HTML"
    )


# ─── Obuna tekshirish callback ─────────────────────────────────────────────────

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if not await is_admin(user_id) and await is_maintenance():
        await callback.answer("⚠️ Bot tamirlanyapti, kuting...", show_alert=True)
        return
    if await check_subscription(user_id, bot):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            async with db.execute("SELECT value FROM bot_settings WHERE key='web_app_url'") as c:
                web_row = await c.fetchone()
            web_url = (web_row[0] if web_row else "") or ""
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Obuna tasdiqlandi!\n\n✨ Xush kelibsiz, <b>{callback.from_user.first_name}</b>!",
            reply_markup=menu_kb(await is_admin(user_id), web_app_url=web_url), parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Siz hali barcha kanallarga obuna bo'lmagansiz!", show_alert=True)


# ─── Anime ko'rsatish (ichki funksiya) ────────────────────────────────────────

async def show_anime(message: Message, anime_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM animelar WHERE id=?", (anime_id,)) as cursor:
            anime = await cursor.fetchone()

    if not anime:
        await message.answer("❌ Ma'lumot topilmadi.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        new_views = (anime[8] or 0) + 1
        await db.execute("UPDATE animelar SET qidiruv=? WHERE id=?", (new_views, anime_id))
        await db.commit()

    # Umumiy qismlarni sanash
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM anime_datas WHERE id=?", (anime_id,)) as count_cs:
            qismlar_soni = (await count_cs.fetchone())[0]

    caption = (
        f"<b>{anime[1]}</b>\n"
        f"╭───────────\n"
        f"├ <b>Qism:</b> {qismlar_soni} ta\n"
        f"├ <b>Holati:</b> {anime[10] if anime[10] else 'OnGoing'}\n"
        f"├ <b>Ovoz:</b> {anime[11] if anime[11] else 'Ovoz berilmagan'}\n"
        f"╰ <b>Janrlari:</b> {anime[7]}"
    )

    try:
        await message.answer_photo(
            photo=anime[2], caption=caption,
            reply_markup=download_kb(anime_id), parse_mode="HTML"
        )
    except:
        try:
            await message.answer_video(
                video=anime[2], caption=caption,
                reply_markup=download_kb(anime_id), parse_mode="HTML"
            )
        except:
            await message.answer(
                f"{caption}", reply_markup=download_kb(anime_id), parse_mode="HTML"
            )


# ─── Anime izlash menyusi ──────────────────────────────────────────────────────

@router.message(F.text == "🔎 Anime izlash")
async def search_anime_menu(message: Message):
    if not await is_admin(message.from_user.id) and await is_maintenance():
        await message.answer(MAINTENANCE_MSG, parse_mode="HTML")
        return
    await message.answer("<b>🔍 Qidiruv turini tanlang:</b>",
                         reply_markup=search_type_kb(), parse_mode="HTML")


# ─── Nom orqali izlash ────────────────────────────────────────────────────────

@router.callback_query(F.data == "searchByName")
async def search_by_name_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>🔎 Anime nomini yuboring:</b>", parse_mode="HTML")
    await state.set_state(UserStates.search_by_name)
    await callback.answer()


@router.message(UserStates.search_by_name)
async def process_search_by_name(message: Message, state: FSMContext):
    query = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM animelar WHERE nom LIKE ? LIMIT 10", (f"%{query}%",)
        ) as cursor:
            results = await cursor.fetchall()

    await state.clear()

    if not results:
        await message.answer("<b>Hech narsa topilmadi 😔</b>", parse_mode="HTML")
        return

    buttons = [
        [InlineKeyboardButton(text=f"{i+1}. {a[1]}", callback_data=f"loadAnime={a[0]}")]
        for i, a in enumerate(results)
    ]
    await message.answer(
        "<b>⬇️ Qidiruv natijalari:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )


# ─── Kod orqali izlash ───────────────────────────────────────────────────────

@router.callback_query(F.data == "searchByCode")
async def search_by_code_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>🔢 Anime kodini yuboring:</b>", parse_mode="HTML")
    await state.set_state(UserStates.search_by_code)
    await callback.answer()


@router.message(UserStates.search_by_code)
async def process_search_by_code(message: Message, state: FSMContext):
    await state.clear()
    if not message.text.isdigit():
        await message.answer("❌ Raqam kiriting!")
        return
    await show_anime(message, int(message.text))


# ─── Janr orqali izlash ──────────────────────────────────────────────────────

@router.callback_query(F.data == "searchByGenre")
async def search_by_genre_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>🎞 Janrni yuboring:</b>\n\n<i>Masalan: Drama, Fantastika, Romantika</i>",
        parse_mode="HTML"
    )
    await state.set_state(UserStates.search_by_genre)
    await callback.answer()


@router.message(UserStates.search_by_genre)
async def process_search_by_genre(message: Message, state: FSMContext):
    query = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM animelar WHERE janri LIKE ? LIMIT 10", (f"%{query}%",)
        ) as cursor:
            results = await cursor.fetchall()

    await state.clear()

    if not results:
        await message.answer("<b>Bu janrda hech narsa topilmadi 😔</b>", parse_mode="HTML")
        return

    buttons = [
        [InlineKeyboardButton(text=f"{i+1}. {a[1]}", callback_data=f"loadAnime={a[0]}")]
        for i, a in enumerate(results)
    ]
    await message.answer(
        f"<b>🎞 «{query}» janridagi animelar:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )


# ─── So'nggi yuklanganlar ────────────────────────────────────────────────────

@router.callback_query(F.data == "lastUploads")
async def last_uploads_callback(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, nom FROM animelar ORDER BY id DESC LIMIT 10"
        ) as cursor:
            results = await cursor.fetchall()

    if not results:
        await callback.answer("Hozircha anime yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(text=f"{i+1}. {a[1]}", callback_data=f"loadAnime={a[0]}")]
        for i, a in enumerate(results)
    ]
    await callback.message.answer(
        "<b>⏱ So'nggi yuklangan animelar:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


# ─── Eng ko'p ko'rilgan ──────────────────────────────────────────────────────

@router.callback_query(F.data == "topViewers")
async def top_viewers_callback(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, nom, qidiruv FROM animelar ORDER BY qidiruv DESC LIMIT 10"
        ) as cursor:
            results = await cursor.fetchall()

    if not results:
        await callback.answer("Hozircha anime yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{i+1}. {a[1]} 👁{a[2]}", callback_data=f"loadAnime={a[0]}"
        )]
        for i, a in enumerate(results)
    ]
    await callback.message.answer(
        "<b>👁️ Eng ko'p ko'rilgan animelar:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


# ─── Barcha animelar ────────────────────────────────────────────────────────

@router.callback_query(F.data == "allAnimes")
async def all_animes_callback(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, nom FROM animelar ORDER BY nom ASC LIMIT 20"
        ) as cursor:
            results = await cursor.fetchall()

    if not results:
        await callback.answer("Hozircha anime yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(text=f"📺 {a[1]}", callback_data=f"loadAnime={a[0]}")]
        for a in results
    ]
    await callback.message.answer(
        "<b>📚 Barcha animelar (alifbo tartibida):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


# ─── Anime yuklash (callback) ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("loadAnime="))
async def load_anime_callback(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id) and await is_maintenance():
        await callback.answer("⚠️ Bot tamirlanyapti, kuting...", show_alert=True)
        return
    anime_id = int(callback.data.split("=")[1])
    try:
        await callback.message.delete()
    except:
        pass
    await show_anime(callback.message, anime_id)
    await callback.answer()


# ─── Qism yuklash ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("yuklanolish="))
async def episode_list_callback(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id) and await is_maintenance():
        await callback.answer("⚠️ Bot tamirlanyapti, kuting...", show_alert=True)
        return
    parts = callback.data.split("=")
    anime_id = int(parts[1])
    ep_num = int(parts[2]) if len(parts) > 2 else 1

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM anime_datas WHERE id=? AND qism=?", (anime_id, ep_num)
        ) as cursor:
            episode_data = await cursor.fetchone()

        async with db.execute("SELECT nom FROM animelar WHERE id=?", (anime_id,)) as cursor:
            anime_name = await cursor.fetchone()
            anime_name = anime_name[0] if anime_name else "Unknown"

        async with db.execute(
            "SELECT qism FROM anime_datas WHERE id=? ORDER BY qism ASC", (anime_id,)
        ) as cursor:
            all_eps = await cursor.fetchall()
            all_eps_list = [{'qism': row[0]} for row in all_eps]

    if not episode_data:
        await callback.answer("❌ Qism topilmadi", show_alert=True)
        return

    file_id = episode_data[2]

    # Qaysi sahifada ekanini avtomatik hisoblash
    from keyboards import EPISODES_PER_PAGE
    all_ep_nums = [int(e['qism']) for e in all_eps_list]
    ep_index = all_ep_nums.index(ep_num) if ep_num in all_ep_nums else 0
    page = ep_index // EPISODES_PER_PAGE

    # Agar bu sahifaning OXIRGI qismi bo'lsa va keyingi sahifa bo'lsa — keyingi sahifaga o't
    total_pages = max(1, (len(all_ep_nums) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE)
    page_last_index = (page + 1) * EPISODES_PER_PAGE - 1
    if ep_index == min(page_last_index, len(all_ep_nums) - 1) and page < total_pages - 1:
        page = page + 1

    kb = episodes_kb(anime_id, ep_num, all_eps_list, page)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        await callback.message.answer_video(
            video=file_id,
            caption=f"<b>{anime_name}</b>\n<i>{ep_num} - qism</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.answer_document(
                document=file_id,
                caption=f"<b>{anime_name}</b>\n<i>{ep_num} - qism</i>",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception as e:
            await callback.answer(f"Xatolik: {e}", show_alert=True)


# ─── Qismlar sahifalash (pagination tugmalari) ────────────────────────────────

@router.callback_query(F.data.startswith("ep_page="))
async def ep_page_callback(callback: CallbackQuery):
    parts = callback.data.split("=")
    anime_id = int(parts[1])
    page = int(parts[2])
    current_ep = int(parts[3])

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT qism FROM anime_datas WHERE id=? ORDER BY qism ASC", (anime_id,)
        ) as cursor:
            all_eps = await cursor.fetchall()
            all_eps_list = [{'qism': row[0]} for row in all_eps]

    kb = episodes_kb(anime_id, current_ep, all_eps_list, page)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()





# ─── Menyu tugmalari ─────────────────────────────────────────────────────────

@router.message(F.text == "💎 VIP")
async def vip_menu(message: Message):
    text = (
        "<b>💎 VIP a'zolik imtiyozlari:</b>\n\n"
        "✅ Barcha animelarga cheksiz kirish\n"
        "✅ Reklama ko'rsatilmaydi\n"
        "✅ Yangi epizodlar birinchi bo'lib keladi\n\n"
        "<i>VIP xaridi uchun admin bilan bog'laning.</i>"
    )
    await message.answer(text, parse_mode="HTML")


# ─── Hisobim (kengaytirilgan) ──────────────────────────────────────────────────────────────

@router.message(F.text == "💰 Hisobim")
async def my_balance(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pul, pul2, odam, status FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        async with db.execute("SELECT kun, date FROM vip_status WHERE user_id=?", (user_id,)) as c:
            vip = await c.fetchone()

    if not user:
        await message.answer("❌ Siz ro'yxatdan o'tmagansiz. /start ni bosing.")
        return

    ref_link = f"https://t.me/{(await message.bot.get_me()).username}?start={user_id}"
    vip_line = f"\n💎 VIP: <b>{vip[1]} dan {vip[0]} kun</b>" if vip else ""

    text = (
        f"<b>💰 Mening hisobim</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Status: <b>{user[3]}</b>{vip_line}\n"
        f"💵 Balans: <b>{user[0]}</b> so'm\n"
        f"🎁 Bonus: <b>{user[1]}</b> so'm\n"
        f"👥 Taklif qilinganlar: <b>{user[2]}</b> kishi\n\n"
        f"🔗 Referal link:\n<code>{ref_link}</code>"
    )
    await message.answer(text, parse_mode="HTML")


# ─── Pul kiritish (to'lov tizimi) ───────────────────────────────────────────────

@router.message(F.text == "➕ Pul kiritish")
async def deposit_menu(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_texts WHERE key='wallet'") as cursor:
            row = await cursor.fetchone()
            wallet_text = row[0] if row else "Hali hamyon o'rnatilmagan."

    await message.answer(
        f"<b>➕ Hisobni to'ldirish</b>\n\n"
        f"To'lov uchun hamyon:\n<code>{wallet_text}</code>\n\n"
        f"<i>Qancha pul kiritmoqchisiz? (raqam kiriting):</i>",
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.enter_amount)


@router.message(PaymentStates.enter_amount, F.text)
async def deposit_enter_amount(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 1000:
        await message.answer("❌ Kamida 1000 so'm kiriting! Faqat raqam yozing.")
        return
    await state.update_data(deposit_amount=int(message.text))
    await message.answer(
        f"📸 Endi to'lov chekini (screenshot yoki kvitansiya) yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.send_check)


@router.message(PaymentStates.send_check, F.photo | F.document)
async def deposit_check_received(message: Message, state: FSMContext, bot: Bot):
    data  = await state.get_data()
    user_id = message.from_user.id
    amount  = data.get('deposit_amount', 0)
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments (user_id, amount, purpose, status, check_file_id) VALUES (?,?,?,?,?)",
            (user_id, amount, "balance", "pending", file_id)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as c:
            pay_id = (await c.fetchone())[0]

    await message.answer("✅ Chek qabul qilindi! Admin tez orada tasdiqlaydi.")

    notify_ids = list(ADMIN_IDS) + [SUPER_ADMIN_ID]
    for admin_id in set(notify_ids):
        try:
            await bot.send_photo(
                admin_id, file_id,
                caption=(
                    f"💳 <b>Balans to'ldirilishi</b>\n\n"
                    f"👤 User: <code>{user_id}</code>\n"
                    f"💰 Summa: <b>{amount} so'm</b>\n"
                    f"🆔 To'lov ID: #{pay_id}"
                ),
                reply_markup=payment_confirm_kb(pay_id),
                parse_mode="HTML"
            )
        except:
            pass
    await state.clear()



# ─── Referal tizimi ────────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Referal")
async def referal_menu(message: Message, bot: Bot):
    user_id  = message.from_user.id
    me       = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={user_id}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT odam, pul2 FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
        async with db.execute("SELECT value FROM bot_settings WHERE key='referral_bonus'") as c:
            bonus_row = await c.fetchone()

    invited = row[0] if row else 0
    earned  = row[1] if row else 0
    bonus   = bonus_row[0] if bonus_row else 500

    text = (
        f"<b>👥 Referal tizimi</b>\n\n"
        f"Har bir do'stingiz uchun <b>{bonus} so'm</b> bonus olasiz!\n\n"
        f"👥 Taklif qilganlaringiz: <b>{invited}</b> kishi\n"
        f"💰 Jami ishlab topgan: <b>{earned}</b> so'm\n\n"
        f"🔗 Sizning referal havolangiz:\n"
        f"<code>{ref_link}</code>"
    )
    await message.answer(text, parse_mode="HTML")


# ─── Cashback ────────────────────────────────────────────────────────────────────

@router.message(F.text == "🎁 Cashback")
async def cashback_menu(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pul2 FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
        async with db.execute("SELECT value FROM bot_settings WHERE key='cashback_percent'") as c:
            pct_row = await c.fetchone()

    bonus  = row[0] if row else 0
    pct    = pct_row[0] if pct_row else 5

    text = (
        f"<b>🎁 Cashback tizimi</b>\n\n"
        f"Har bir to'lovdan <b>{pct}%</b> cashback olasiz!\n"
        f"Cashback bonus sifatida hisoblanadi.\n\n"
        f"💰 Sizning cashback balansiz: <b>{bonus}</b> so'm"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📚 Qo'llanma")
async def guide_menu(message: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_texts WHERE key='guide'") as cursor:
            row = await cursor.fetchone()
            guide_text = row[0] if row else "📚 Qo'llanma matni hali kiritilmagan."

    await message.answer(f"<b>📚 Qo'llanma</b>\n\n{guide_text}", parse_mode="HTML")


@router.message(F.text == "💵 Reklama va Homiylik")
async def ads_menu(message: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_texts WHERE key='ads'") as cursor:
            row = await cursor.fetchone()
            ads_text = row[0] if row else "💵 Reklama matni hali kiritilmagan."

    await message.answer(f"<b>💵 Reklama</b>\n\n{ads_text}", parse_mode="HTML")



# ─── Null callback (hech narsa qilmaydigan) ──────────────────────────────────

@router.callback_query(F.data == "null")
async def null_callback(callback: CallbackQuery):
    await callback.answer()


# ─── Yopish callback ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "close")
async def close_callback(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()
