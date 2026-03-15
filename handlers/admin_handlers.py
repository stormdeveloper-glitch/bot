import aiosqlite
import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS, SUPER_ADMIN_ID, DB_PATH
from keyboards import panel_kb, boshqarish_kb, menu_kb
from states import AdminStates, EditAnimeStates, SettingsStates, ButtonStates, PostStates
from utils import is_admin, is_super_admin

router = Router()


# ─── Panel kirish ────────────────────────────────────────────────────────────

@router.message(Command("panel"))
async def cmd_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("<b>🗄 Admin paneliga xush kelibsiz!</b>",
                         reply_markup=panel_kb(), parse_mode="HTML")


@router.message(F.text == "🗄 Boshqarish")
async def text_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("<b>🗄 Admin paneliga xush kelibsiz!</b>",
                         reply_markup=panel_kb(), parse_mode="HTML")


# ─── Orqaga ──────────────────────────────────────────────────────────────────

@router.message(F.text == "◀️ Orqaga")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🏠 Bosh menyu",
        reply_markup=menu_kb(await is_admin(message.from_user.id))
    )


# ─── Statistika ──────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def statistics_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE ban='unban'") as c:
            active_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE ban='ban'") as c:
            banned_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM animelar") as c:
            total_animes = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM anime_datas") as c:
            total_episodes = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM vip_status") as c:
            vip_users = (await c.fetchone())[0]

    text = (
        f"<b>📊 Bot statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"✅ Faol: <b>{active_users}</b>\n"
        f"🚫 Banned: <b>{banned_users}</b>\n"
        f"💎 VIP: <b>{vip_users}</b>\n\n"
        f"🎬 Jami animelar: <b>{total_animes}</b>\n"
        f"📺 Jami qismlar: <b>{total_episodes}</b>\n"
    )
    await message.answer(text, parse_mode="HTML")


# ─── Xabar yuborish (broadcast) ──────────────────────────────────────────────

@router.message(F.text == "✉ Xabar Yuborish")
async def broadcast_prompt(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "<b>✉ Barcha foydalanuvchilarga yubormoqchi bo'lgan xabarni yuboring:</b>\n\n"
        "<i>Matn, rasm yoki video yuborishingiz mumkin.</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.broadcast)


@router.message(AdminStates.broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE ban='unban'") as cursor:
            users = await cursor.fetchall()

    sent = 0
    failed = 0
    for (user_id,) in users:
        try:
            await message.copy_to(user_id)
            sent += 1
        except:
            failed += 1

    await message.answer(
        f"✅ Xabar yuborildi!\n\n"
        f"📤 Yuborildi: <b>{sent}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>",
        reply_markup=panel_kb(), parse_mode="HTML"
    )


# ─── Bot holati ───────────────────────────────────────────────────────────────

# ─── Bot holati ───────────────────────────────────────────────────────────────

@router.message(F.text == "🤖 Bot holati")
async def bot_status_handler(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
        return
    me = await bot.get_me()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key='bot_maintenance'") as cursor:
            row = await cursor.fetchone()
            maintenance = row[0] == "1" if row else False

    status_icon = "🔴 O'chirilgan (Texnik ishlar)" if maintenance else "✅ Ishlamoqda"
    toggle_text = "✅ Botni Yoqish" if maintenance else "🔴 Botni O'chirish"
    toggle_cb = "botTurnOn" if maintenance else "botTurnOff"

    text = (
        f"<b>🤖 Bot holati: {status_icon}</b>\n\n"
        f"👤 Ismi: {me.full_name}\n"
        f"🔗 Username: @{me.username}\n"
        f"🆔 ID: <code>{me.id}</code>\n"
        f"🕐 Vaqt: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
    )
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb)]
    ])
    await message.answer(text, reply_markup=btn, parse_mode="HTML")


@router.callback_query(F.data.in_({"botTurnOff", "botTurnOn"}))
async def toggle_bot_maintenance(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id):
        return

    turning_off = callback.data == "botTurnOff"
    new_val = "1" if turning_off else "0"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('bot_maintenance', ?)",
            (new_val,)
        )
        await db.commit()

    me = await bot.get_me()
    status_icon = "🔴 O'chirilgan (Texnik ishlar)" if turning_off else "✅ Ishlamoqda"
    toggle_text = "✅ Botni Yoqish" if turning_off else "🔴 Botni O'chirish"
    toggle_cb = "botTurnOn" if turning_off else "botTurnOff"

    text = (
        f"<b>🤖 Bot holati: {status_icon}</b>\n\n"
        f"👤 Ismi: {me.full_name}\n"
        f"🔗 Username: @{me.username}\n"
        f"🆔 ID: <code>{me.id}</code>\n"
        f"🕐 Vaqt: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
    )
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb)]
    ])
    action = "🔴 O'chirildi! Foydalanuvchilar texnik ish xabarini ko'radi." if turning_off else "✅ Yoqildi! Foydalanuvchilar botdan foydalana oladi."
    await callback.message.edit_text(text, reply_markup=btn, parse_mode="HTML")
    await callback.answer(action, show_alert=True)



# ─── Kanallar boshqarish ─────────────────────────────────────────────────────

@router.message(F.text == "📢 Kanallar")
async def channels_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM channels") as cursor:
            channels = await cursor.fetchall()

    if not channels:
        text = "<b>📢 Hozircha kanal qo'shilmagan</b>"
    else:
        text = "<b>📢 Qo'shilgan kanallar:</b>\n\n"
        for ch in channels:
            ctype = ""
            if ch[2] == "public": ctype = "Majburiy ochiq"
            elif ch[2] == "request": ctype = "Zayavka yopiq"
            elif ch[2] == "social": ctype = "Ijtimoiy"
            elif ch[2] == "anime": ctype = "Anime"
            elif ch[2] == "ongoing": ctype = "🔸 Ongoing"
            text += f"[{ctype}] ID: <code>{ch[1]}</code> | 🔗 <a href='{ch[3]}'>Link</a>\n"

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Majburiy kanal (ochiq)", callback_data="addChannelType=public")],
        [InlineKeyboardButton(text="➕ Zayavka kanal (yopiq)", callback_data="addChannelType=request")],
        [InlineKeyboardButton(text="➕ Ijtimoiy tarmoq", callback_data="addChannelType=social")],
        [InlineKeyboardButton(text="➕ Anime kanal", callback_data="addChannelType=anime")],
        [InlineKeyboardButton(text="➕ 🔸 Ongoing kanal", callback_data="addChannelType=ongoing")],
        [InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="removeChannel")]
    ])
    await message.answer(text, reply_markup=buttons, parse_mode="HTML")


@router.callback_query(F.data.startswith("addChannelType="))
async def add_channel_prompt(callback: CallbackQuery, state: FSMContext):
    ctype = callback.data.split("=")[1]
    await state.update_data(channel_type=ctype)
    await callback.message.answer(
        "<b>Kanal ID sini yuboring</b>\n\n"
        "<i>Misol: -1001234567890</i>\n\n"
        "Kanal ID ni bilish uchun @username_to_id_bot dan foydalaning.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_channel_id)
    await callback.answer()


@router.message(AdminStates.add_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    await state.update_data(channel_id=message.text)
    await message.answer("<b>Kanal linkini yuboring:</b>\n\n<i>Misol: https://t.me/kanal_nomi</i>", parse_mode="HTML")
    await state.set_state(AdminStates.add_channel_link)


@router.message(AdminStates.add_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data['channel_id']
    channel_type = data.get('channel_type', 'public')
    channel_link = message.text

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO channels (channelId, channelType, channelLink) VALUES (?, ?, ?)",
            (channel_id, channel_type, channel_link)
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ Kanal qo'shildi!\n\n🆔 ID: <code>{channel_id}</code> | Turi: <b>{channel_type}</b>",
        reply_markup=panel_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data == "removeChannel")
async def remove_channel_prompt(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM channels") as cursor:
            channels = await cursor.fetchall()

    if not channels:
        await callback.answer("Kanallar yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"🗑 {ch[1]} ({ch[2]})", callback_data=f"delChannel={ch[0]}"
        )]
        for ch in channels
    ]
    await callback.message.answer(
        "<b>O'chirish uchun kanal tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delChannel="))
async def delete_channel_callback(callback: CallbackQuery):
    channel_db_id = int(callback.data.split("=")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE id=?", (channel_db_id,))
        await db.commit()
    await callback.message.edit_text("✅ Kanal o'chirildi!", parse_mode="HTML")
    await callback.answer()


# ─── Foydalanuvchini boshqarish ──────────────────────────────────────────────

@router.message(F.text == "🔎 Foydalanuvchini boshqarish")
async def manage_user_prompt(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "<b>🔎 Foydalanuvchi ID sini yuboring:</b>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.manage_user)


@router.message(AdminStates.manage_user)
async def process_manage_user(message: Message, state: FSMContext):
    await state.clear()
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    user_id = int(message.text)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()

    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        return

    status_text = "🚫 Ban" if user[6] == "ban" else "✅ Faol"
    ban_btn_text = "✅ Ban olib tashla" if user[6] == "ban" else "🚫 Ban qil"
    ban_cb = f"unbanUser={user_id}" if user[6] == "ban" else f"banUser={user_id}"

    text = (
        f"<b>👤 Foydalanuvchi ma'lumotlari</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📊 Status: {user[3]}\n"
        f"🚦 Holat: {status_text}\n"
        f"💵 Balans: {user[2]}\n"
        f"👥 Taklif qilganlari: {user[5]}\n"
    )
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ban_btn_text, callback_data=ban_cb)]
    ])
    await message.answer(text, reply_markup=buttons, parse_mode="HTML")


@router.callback_query(F.data.startswith("banUser="))
async def ban_user(callback: CallbackQuery):
    user_id = int(callback.data.split("=")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET ban='ban' WHERE user_id=?", (user_id,))
        await db.commit()
    await callback.message.edit_text(f"🚫 Foydalanuvchi <code>{user_id}</code> banlandi!", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("unbanUser="))
async def unban_user(callback: CallbackQuery):
    user_id = int(callback.data.split("=")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET ban='unban' WHERE user_id=?", (user_id,))
        await db.commit()
    await callback.message.edit_text(f"✅ Foydalanuvchi <code>{user_id}</code> dan ban olindi!", parse_mode="HTML")
    await callback.answer()


# ─── Anime qo'shish flow ─────────────────────────────────────────────────────

@router.message(F.text == "🎥 Animelar sozlash")
async def anime_settings(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="addAnime")],
        [InlineKeyboardButton(text="➕ Qism qo'shish", callback_data="addEpisode")],
        [InlineKeyboardButton(text="🗑 ID orqali animeni o'chirish", callback_data="deleteAnimeByCode")],
    ])
    await message.answer("<b>🎥 Animelar boshqaruvi:</b>", reply_markup=buttons, parse_mode="HTML")


@router.callback_query(F.data == "addAnime")
async def start_add_anime(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>Anime nomini kiriting:</b>", reply_markup=boshqarish_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.add_anime_name)
    await callback.answer()


@router.message(AdminStates.add_anime_name)
async def process_anime_name(message: Message, state: FSMContext):
    await state.update_data(nom=message.text)
    await message.answer("<b>🎥 Jami qismlar sonini kiriting:</b>", reply_markup=boshqarish_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.add_anime_episodes)


@router.message(AdminStates.add_anime_episodes)
async def process_anime_episodes(message: Message, state: FSMContext):
    await state.update_data(qismi=message.text)
    await message.answer("<b>🌍 Qaysi davlat ishlab chiqarganini kiriting:</b>", reply_markup=boshqarish_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.add_anime_country)


@router.message(AdminStates.add_anime_country)
async def process_anime_country(message: Message, state: FSMContext):
    await state.update_data(davlat=message.text)
    await message.answer("<b>🇺🇿 Qaysi tilda ekanligini kiriting:</b>", reply_markup=boshqarish_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.add_anime_language)


@router.message(AdminStates.add_anime_language)
async def process_anime_language(message: Message, state: FSMContext):
    await state.update_data(tili=message.text)
    await message.answer("<b>📆 Qaysi yilda ishlab chiqarilganini kiriting:</b>", reply_markup=boshqarish_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.add_anime_year)


@router.message(AdminStates.add_anime_year)
async def process_anime_year(message: Message, state: FSMContext):
    await state.update_data(yili=message.text)
    await message.answer(
        "<b>🎞 Janrlarini kiriting:</b>\n\n<i>Na'muna: Drama, Fantastika</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_anime_genre)


@router.message(AdminStates.add_anime_genre)
async def process_anime_genre(message: Message, state: FSMContext):
    await state.update_data(janri=message.text)
    await message.answer(
        "<b>🎙️ Fandub nomini kiriting:</b>\n\n<i>Na'muna: @AnimeLiveUz</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_anime_fandub)


@router.message(AdminStates.add_anime_fandub)
async def process_anime_fandub(message: Message, state: FSMContext):
    await state.update_data(fandub=message.text)
    await message.answer(
        "<b>📊 Anime holatini kiriting:</b>\n\n<i>Na'muna: 🔸 OnGoing yoki ✅ Yakunlangan</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_anime_status)


@router.message(AdminStates.add_anime_status)
async def process_anime_status(message: Message, state: FSMContext):
    await state.update_data(status=message.text)
    await message.answer(
        "<b>🏞 Rasmini yoki 60 soniyadan oshmagan video yuboring:</b>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_anime_picture)


@router.message(AdminStates.add_anime_picture, F.photo | F.video | F.document)
async def process_anime_picture(message: Message, state: FSMContext):
    data = await state.get_data()
    
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.document:
        if message.document.mime_type and (message.document.mime_type.startswith("image/") or message.document.mime_type.startswith("video/")):
            file_id = message.document.file_id
        else:
            await message.answer("❌ Iltimos, faqat rasm yoki video yuboring (fayl ko'rinishida bo'lsa ham)!")
            return
    else:
        await message.answer("❌ Fayl topilmadi!")
        return
        
    sana = datetime.datetime.now().strftime("%H:%M %d.%m.%Y")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO animelar (nom, rams, qismi, davlat, tili, yili, janri, qidiruv, aniType, fandub, sana)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (data['nom'], file_id, data['qismi'], data['davlat'], data['tili'],
              data['yili'], data['janri'], data['status'], data['fandub'], sana))
        await db.commit()
        cursor = await db.execute("SELECT last_insert_rowid()")
        anime_id = (await cursor.fetchone())[0]

    await message.answer(
        f"✅ Anime qo'shildi!\n\n<b>Anime kodi:</b> <code>{anime_id}</code>",
        reply_markup=panel_kb(), parse_mode="HTML"
    )
    await state.clear()


# ─── Qism qo'shish flow ──────────────────────────────────────────────────────

@router.callback_query(F.data == "addEpisode")
async def start_add_episode(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>📺 Qism qo'shish</b>\n\nAnime kodini (ID) kiriting:",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_episode_code)
    await callback.answer()


# ─── ID orqali animeni to'liq o'chirish ──────────────────────────────────────

@router.callback_query(F.data == "deleteAnimeByCode")
async def delete_anime_by_code_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>🗑 ID orqali animeni o'chirish</b>\n\n"
        "Anime kodini (ID) kiriting:\n\n"
        "<i>⚠️ Diqqat: Anime va unga tegishli BARCHA qismlar o'chib ketadi!</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.delete_anime_by_code)
    await callback.answer()


@router.message(AdminStates.delete_anime_by_code)
async def process_delete_anime_by_code(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    anime_id = int(message.text)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT nom, qismi FROM animelar WHERE id=?", (anime_id,)) as cursor:
            anime = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM anime_datas WHERE id=?", (anime_id,)) as cursor:
            ep_count = (await cursor.fetchone())[0]

    if not anime:
        await message.answer(f"❌ <b>{anime_id}</b> kodli anime topilmadi!", parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(del_anime_id=anime_id)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ Ha, o'chirilsin ({ep_count} qism bilan)",
            callback_data=f"confirmDelByCode={anime_id}"
        )],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancelDelByCode")]
    ])
    await message.answer(
        f"⚠️ <b>Tasdiqlang:</b>\n\n"
        f"🎬 Anime: <b>{anime[0]}</b>\n"
        f"🆔 Kod: <code>{anime_id}</code>\n"
        f"📺 Qismlar: <b>{ep_count} ta</b>\n\n"
        f"Bu anime va barcha qismlari <b>butunlay o'chib ketadi!</b>",
        reply_markup=confirm_kb, parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data.startswith("confirmDelByCode="))
async def confirm_delete_by_code(callback: CallbackQuery):
    anime_id = int(callback.data.split("=")[1])

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT nom FROM animelar WHERE id=?", (anime_id,)) as cursor:
            row = await cursor.fetchone()
        anime_nom = row[0] if row else str(anime_id)

        await db.execute("DELETE FROM animelar WHERE id=?", (anime_id,))
        await db.execute("DELETE FROM anime_datas WHERE id=?", (anime_id,))
        await db.commit()

    await callback.message.edit_text(
        f"✅ <b>{anime_nom}</b> va unga tegishli barcha qismlar o'chirildi!",
        parse_mode="HTML"
    )
    await callback.answer("✅ O'chirildi!", show_alert=True)


@router.callback_query(F.data == "cancelDelByCode")
async def cancel_delete_by_code(callback: CallbackQuery):
    await callback.message.edit_text("❌ O'chirish bekor qilindi.")
    await callback.answer()


@router.message(AdminStates.add_episode_code)
async def process_episode_code(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    anime_id = int(message.text)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT nom, qismi FROM animelar WHERE id=?", (anime_id,)) as cursor:
            anime = await cursor.fetchone()

    if not anime:
        await message.answer("❌ Bunday ID li anime topilmadi!")
        return

    await state.update_data(anime_id=anime_id, anime_nom=anime[0])

    # Qaysi qism ekanligini so'rash
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT MAX(qism) FROM anime_datas WHERE id=?", (anime_id,)
        ) as cursor:
            max_ep = await cursor.fetchone()
            next_ep = (max_ep[0] or 0) + 1

    await message.answer(
        f"✅ Anime: <b>{anime[0]}</b>\n\n"
        f"📺 Keyingi qism raqami: <b>{next_ep}</b>\n\n"
        f"Shu qismni yuborasizmi? Boshqa raqam kiritmoqchi bo'lsangiz raqamni yuboring:",
        parse_mode="HTML"
    )
    await state.update_data(ep_num=next_ep)
    await state.set_state(AdminStates.add_episode_file)

    # Agar admin raqamni o'zgartirmoqchi bo'lsa
@router.message(AdminStates.add_episode_file, F.text)
async def change_episode_number(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return
        
    new_ep = int(message.text)
    await state.update_data(ep_num=new_ep)
    
    data = await state.get_data()
    await message.answer(
        f"✅ Qism raqami <b>{new_ep}</b> ga o'zgartirildi.\n\n"
        f"Endi <b>{data['anime_nom']}</b> uchun {new_ep}-qism videosini yuboring:",
        parse_mode="HTML"
    )


@router.message(AdminStates.add_episode_file, F.video | F.document)
async def process_episode_file(message: Message, state: FSMContext, bot: Bot):
    if message.document:
        if not (message.document.mime_type and message.document.mime_type.startswith("video/")):
            await message.answer("❌ Iltimos, faqat video fayl yuboring!")
            return
        file_id = message.document.file_id
    else:
        file_id = message.video.file_id

    data = await state.get_data()
    anime_id = data['anime_id']
    ep_num = data['ep_num']
    file_id = message.video.file_id
    sana = datetime.datetime.now().strftime("%H:%M %d.%m.%Y")

    async with aiosqlite.connect(DB_PATH) as db:
        # Avval bu qism mavjudligini tekshir
        async with db.execute(
            "SELECT id FROM anime_datas WHERE id=? AND qism=?", (anime_id, ep_num)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await db.execute(
                "UPDATE anime_datas SET file_id=?, sana=? WHERE id=? AND qism=?",
                (file_id, sana, anime_id, ep_num)
            )
        else:
            await db.execute(
                "INSERT INTO anime_datas (id, file_id, qism, sana) VALUES (?, ?, ?, ?)",
                (anime_id, file_id, ep_num, sana)
            )
        await db.commit()

    # Barcha ma'lumotlarni yig'ish
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT nom, janri, rams, qismi, aniType, fandub FROM animelar WHERE id=?", (anime_id,)) as cursor:
            anime_info = await cursor.fetchone()
        # Hozir nechta qism yuklangan
        async with db.execute("SELECT COUNT(*) FROM anime_datas WHERE id=?", (anime_id,)) as cursor:
            uploaded_count = (await cursor.fetchone())[0]

    next_ep = ep_num + 1
    await state.update_data(ep_num=next_ep)

    await message.answer(
        f"✅ <b>{data['anime_nom']}</b> — {ep_num}-qism qo'shildi! ({uploaded_count}/{anime_info[3] if anime_info else '?'} qism yuklandi)\n\n"
        f"🎞 Endi <b>{next_ep}-qism</b> videosini yuboring:\n"
        f"<i>To'xtatish uchun qaytish tugmasini yoki /panel ni bosing.</i>",
        reply_markup=panel_kb(), parse_mode="HTML"
    )

    # Auto-post logikasi
    from config import MAIN_CHANNEL_ID, BOT_USERNAME, MAIN_CHANNEL_USERNAME
    if anime_info:
        nom, janri, rams, total_qism, status, fandub = anime_info
        fandub = fandub or "Ovoz berilmagan"

        try:
            total_qism_int = int(total_qism)
        except (ValueError, TypeError):
            total_qism_int = None

        # ── Ongoing: qism raqami dastlabki miqdordan oshgan bo'lsa ────────
        if total_qism_int and ep_num > total_qism_int:
            async with aiosqlite.connect(DB_PATH) as db_ch:
                async with db_ch.execute(
                    "SELECT channelId FROM channels WHERE channelType='ongoing' LIMIT 1"
                ) as cur_ch:
                    ongoing_ch = await cur_ch.fetchone()

            if ongoing_ch:
                ongoing_channel_id = ongoing_ch[0]
                ongoing_text = (
                    f"<b>{nom}</b>\n"
                    f"╭───────────\n"
                    f"├ <b>Holati:</b> 🔸 OnGoing\n"
                    f"├ <b>Yangi qism:</b> {ep_num}-qism 🆕\n"
                    f"├ <b>Janrlari:</b> {janri}\n"
                    f"├ <b>Ovoz:</b> {fandub}\n"
                    f"╰───────────"
                )
                watch_btn = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"▶️ {ep_num}-qismni ko'rish",
                        url=f"https://t.me/{BOT_USERNAME}?start={anime_id}_{ep_num}"
                    )]
                ])
                try:
                    await bot.send_photo(
                        chat_id=ongoing_channel_id,
                        photo=rams,
                        caption=ongoing_text,
                        reply_markup=watch_btn,
                        parse_mode="HTML"
                    )
                    await message.answer(f"📢 Ongoing kanal: {ep_num}-qism uchun post yuborildi!")
                except Exception as e:
                    await message.answer(f"⚠️ Ongoing kanalga post yuborilmadi: {e}")
            else:
                await message.answer("⚠️ Ongoing kanal topilmadi! 📢 Kanallar bo'limidan ongoing kanal qo'shing.")

        # ── Barcha qismlar to'liq yuklanganda asosiy kanalga post ──────────
        if MAIN_CHANNEL_ID and total_qism_int and uploaded_count >= total_qism_int:
            post_text = (
                f"<b>{nom}</b>\n"
                f"╭───────────\n"
                f"├ <b>Holati:</b> {status}\n"
                f"├ <b>Qismlar:</b> {total_qism_int} / {total_qism_int} ✅\n"
                f"├ <b>Sifat:</b> 720p - 1080p\n"
                f"├ <b>Janrlari:</b> {janri}\n"
                f"├ <b>Kanal:</b> {MAIN_CHANNEL_USERNAME}\n"
                f"├ <b>Ovoz:</b> {fandub}\n"
                f"╰───────────"
            )

            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Tomosha Qilish ✨", url=f"https://t.me/{BOT_USERNAME}?start={anime_id}")]
            ])

            try:
                await bot.send_photo(
                    chat_id=MAIN_CHANNEL_ID,
                    photo=rams,
                    caption=post_text,
                    reply_markup=btn,
                    parse_mode="HTML"
                )
                await message.answer(f"📢 Barcha {total_qism_int} qism yuklandi — kanal post qilindi!")
                await state.clear()
            except Exception as e:
                await message.answer(f"⚠️ Auto-post kanalga yuborilmadi: {e}\n(Bot u kanalda adminligini tekshiring)")


# ─── Adminlar boshqarish ──────────────────────────────────────────────────

@router.message(F.text == "📋 Adminlar")
async def admins_handler(message: Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Bu bo'lim faqat Super Admin uchun!")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM admins") as cursor:
            admins = await cursor.fetchall()

    text = "<b>📋 Adminlar ro'yxati:</b>\n\n"
    if not admins:
        text += "Hozircha qo'shimcha adminlar yo'q."
    else:
        for adm in admins:
            text += f"🆔 <code>{adm[0]}</code>\n"

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="addAdmin")],
        [InlineKeyboardButton(text="🗑 Admin o'chirish", callback_data="removeAdmin")]
    ])
    await message.answer(text, reply_markup=buttons, parse_mode="HTML")


@router.callback_query(F.data == "addAdmin")
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>Yangi admin foydalanuvchi ID sini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.add_admin)
    await callback.answer()


@router.message(AdminStates.add_admin)
async def process_add_admin(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqamli ID yuboring!")
        return
    
    new_admin_id = int(message.text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", 
                         (new_admin_id, message.from_user.id))
        await db.commit()
    
    await state.clear()
    await message.answer(f"✅ Foydalanuvchi <code>{new_admin_id}</code> admin qilib tayinlandi!", reply_markup=panel_kb(), parse_mode="HTML")


@router.callback_query(F.data == "removeAdmin")
async def remove_admin_prompt(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM admins") as cursor:
            admins = await cursor.fetchall()

    if not admins:
        await callback.answer("Adminlar yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(text=f"🗑 {adm[0]}", callback_data=f"delAdmin={adm[0]}")]
        for adm in admins
    ]
    await callback.message.answer("<b>O'chirish uchun adminni tanlang:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("delAdmin="))
async def delete_admin_callback(callback: CallbackQuery):
    admin_id = int(callback.data.split("=")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (admin_id,))
        await db.commit()
    await callback.message.edit_text(f"✅ Admin <code>{admin_id}</code> o'chirildi!", parse_mode="HTML")
    await callback.answer()


# ─── Matnlar boshqarish ──────────────────────────────────────────────────────

@router.message(F.text == "📃 Matnlar")
async def texts_handler(message: Message):
    if not await is_admin(message.from_user.id): return
    
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Qo'llanma matni", callback_data="edit_text=guide")],
        [InlineKeyboardButton(text="💵 Reklama matni", callback_data="edit_text=ads")]
    ])
    await message.answer("<b>O'zgartirmoqchi bo'lgan bo'lim matnini tanlang:</b>", reply_markup=buttons, parse_mode="HTML")


@router.callback_query(F.data.startswith("edit_text="))
async def edit_text_prompt(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split("=")[1]
    await state.update_data(edit_key=key)
    await callback.message.answer(f"<b>Yangi matnni yuboring ({key}):</b>", parse_mode="HTML")
    await state.set_state(AdminStates.edit_text)
    await callback.answer()


@router.message(AdminStates.edit_text)
async def process_edit_text(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data['edit_key']
    new_text = message.text
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO bot_texts (key, value) VALUES (?, ?)", (key, new_text))
        await db.commit()
    
    await state.clear()
    await message.answer("✅ Matn yangilandi!", reply_markup=panel_kb(), parse_mode="HTML")


@router.message(F.text == "💳 Hamyonlar")
async def wallet_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_texts WHERE key='wallet'") as cursor:
            row = await cursor.fetchone()
            current_wallet = row[0] if row else "Hali o'rnatilmagan"
            
    await message.answer(f"<b>Hozirgi hamyon:</b>\n\n<code>{current_wallet}</code>\n\nYangi hamyon ma'lumotlarini yuboring:", parse_mode="HTML")
    await state.set_state(AdminStates.edit_wallet)


@router.message(AdminStates.edit_wallet)
async def process_edit_wallet(message: Message, state: FSMContext):
    new_wallet = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO bot_texts (key, value) VALUES (?, ?)", ('wallet', new_wallet))
        await db.commit()
    
    await state.clear()
    await message.answer("✅ Hamyon yangilandi!", reply_markup=panel_kb(), parse_mode="HTML")


# ─── Animelar sozlash (Edit/Delete) ──────────────────────────────────────────

@router.message(F.text == "🎥 Animelar sozlash")
async def manage_animes_handler(message: Message):
    if not await is_admin(message.from_user.id): return
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, nom FROM animelar ORDER BY id DESC LIMIT 20") as cursor:
            animes = await cursor.fetchall()

    if not animes:
        await message.answer("Bazada hech qanday anime yo'q!")
        return

    text = "<b>🎬 Boshqarish uchun animeni tanlang:</b>"
    buttons = []
    for anime in animes:
        buttons.append([InlineKeyboardButton(text=f"{anime[1]}", callback_data=f"manageAnime={anime[0]}")])
        
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("manageAnime="))
async def manage_anime_callback(callback: CallbackQuery):
    anime_id = int(callback.data.split("=")[1])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM animelar WHERE id=?", (anime_id,)) as cursor:
            anime = await cursor.fetchone()

    if not anime:
        await callback.answer("Anime topilmadi!", show_alert=True)
        return

    text = (
        f"<b>🎬 Anime: {anime[1]}</b>\n\n"
        f"<b>Holati:</b> {anime[10]}\n"
        f"<b>Janri:</b> {anime[7]}\n"
        f"<b>Yili:</b> {anime[6]}\n\n"
        "Nima qilmoqchisiz?"
    )
    
    buttons = [
        [InlineKeyboardButton(text="📝 Ma'lumotlarni tahrirlash", callback_data=f"editAnimeOpts={anime_id}")],
        [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"prepDelAnime={anime_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="refreshAnimeList")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "refreshAnimeList")
async def refresh_anime_list_callback(callback: CallbackQuery):
    await callback.message.delete()
    await manage_animes_handler(callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith("editAnimeOpts="))
async def edit_anime_options(callback: CallbackQuery):
    anime_id = int(callback.data.split("=")[1])
    
    buttons = [
        [InlineKeyboardButton(text="Nomini o'zgartirish", callback_data=f"editAField={anime_id}=nom")],
        [InlineKeyboardButton(text="Holati (OnGoing/Yakunlangan)", callback_data=f"editAField={anime_id}=aniType")],
        [InlineKeyboardButton(text="Janrini o'zgartirish", callback_data=f"editAField={anime_id}=janri")],
        [InlineKeyboardButton(text="Rasm/Video (Poster)", callback_data=f"editAField={anime_id}=rams")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"manageAnime={anime_id}")]
    ]
    await callback.message.edit_text("<b>Tahrirlash uchun maydonni tanlang:</b>", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("editAField="))
async def edit_anime_field_prompt(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("=")
    anime_id = int(parts[1])
    field = parts[2]
    
    await state.update_data(edit_anime_id=anime_id, edit_field=field)
    
    prompt = f"<b>Yangi qiymatni yuboring ({field}):</b>"
    if field == "rams":
        prompt = "<b>Yangi rasm yoki 60 soniyali video yuboring:</b>"
        
    await callback.message.answer(prompt, parse_mode="HTML")
    await state.set_state(EditAnimeStates.edit_field)
    await callback.answer()


@router.message(EditAnimeStates.edit_field)
async def process_edit_anime_field(message: Message, state: FSMContext):
    data = await state.get_data()
    anime_id = data['edit_anime_id']
    field = data['edit_field']
    
    new_value = None
    if field == "rams":
        if message.photo:
            new_value = message.photo[-1].file_id
        elif message.video:
            new_value = message.video.file_id
        elif message.document and message.document.mime_type and (message.document.mime_type.startswith("image/") or message.document.mime_type.startswith("video/")):
            new_value = message.document.file_id
        else:
            await message.answer("❌ Faqat rasm yoki video yuboring!")
            return
    else:
        new_value = message.text

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE animelar SET {field}=? WHERE id=?", (new_value, anime_id))
        await db.commit()
    
    await state.clear()
    await message.answer("✅ Ma'lumot yangilandi!", reply_markup=panel_kb())


@router.callback_query(F.data.startswith("prepDelAnime="))
async def prepare_delete_anime(callback: CallbackQuery, state: FSMContext):
    anime_id = int(callback.data.split("=")[1])
    
    buttons = [
        [InlineKeyboardButton(text="✅ Ha, o'chirilsin", callback_data=f"execDelAnime={anime_id}")],
        [InlineKeyboardButton(text="❌ Yo'q, qolsin", callback_data=f"manageAnime={anime_id}")]
    ]
    await callback.message.edit_text("<b>⚠️ Diqqat! Ushbu animeni va unga tegishli BARCHA QISMLARNI o'chirib yubormoqchimisiz?</b>",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("execDelAnime="))
async def execute_delete_anime(callback: CallbackQuery):
    anime_id = int(callback.data.split("=")[1])
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Anime o'zi
        await db.execute("DELETE FROM animelar WHERE id=?", (anime_id,))
        # Unga tegishli qismlar
        await db.execute("DELETE FROM anime_datas WHERE id=?", (anime_id,))
        await db.commit()
        
    await callback.message.edit_text("✅ Anime va barcha qismlari butkul o'chirildi!")
    await callback.answer()


# ─── Stub handlerlar (hozircha) ──────────────────────────────────────────────


# ─── *️⃣ Birlamchi sozlamalar ─────────────────────────────────────────────────

SETTINGS_LABELS = {
    "vip_price":      "💰 VIP narxi",
    "vip_currency":   "💱 VIP valyuta",
    "referral_bonus": "👥 Referal bonus (so'm)",
    "cashback_percent": "🎁 Cashback (%)",
    "web_app_url": "🌐 Web App URL (bo'sh = o'chiq)",
    "start_text":     "👋 Start xabari",
}

@router.message(F.text == "*️⃣ Birlamchi sozlamalar")
async def basic_settings_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM bot_settings") as cursor:
            rows = await cursor.fetchall()

    settings = {r[0]: r[1] for r in rows}

    text = "<b>*️⃣ Birlamchi sozlamalar:</b>\n\n"
    for key, label in SETTINGS_LABELS.items():
        val = settings.get(key, "—")
        text += f"{label}: <b>{val}</b>\n"

    buttons = [
        [InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"editSetting={key}")]
        for key, label in SETTINGS_LABELS.items()
    ]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("editSetting="))
async def edit_setting_prompt(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split("=")[1]
    label = SETTINGS_LABELS.get(key, key)
    await state.update_data(setting_key=key)
    await callback.message.answer(
        f"<b>✏️ {label}</b> uchun yangi qiymatni yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.edit_value)
    await callback.answer()


@router.message(SettingsStates.edit_value, F.text)
async def process_setting_value(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("setting_key")
    if not key:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
            (key, message.text)
        )
        await db.commit()

    label = SETTINGS_LABELS.get(key, key)
    await state.clear()
    await message.answer(
        f"✅ <b>{label}</b> yangilandi: <code>{message.text}</code>",
        reply_markup=panel_kb(), parse_mode="HTML"
    )


# ─── 📋 Adminlar ─────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Adminlar")
async def admins_menu(message: Message):
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Bu bo'lim faqat Asosiy Admin uchun!")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, added_by FROM admins") as cursor:
            admins_list = await cursor.fetchall()

    if not admins_list:
        text = "<b>📋 Qo'shimcha adminlar yo'q.</b>"
    else:
        text = "<b>📋 Tasdiqlangan Adminlar:</b>\n\n"
        for a in admins_list:
            text += f"👤 ID: <code>{a[0]}</code> (Qo'shgan: {a[1]})\n"

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="addAdmin_prompt")],
        [InlineKeyboardButton(text="🗑 Admin o'chirish", callback_data="removeAdmin_prompt")]
    ])
    await message.answer(text, reply_markup=buttons, parse_mode="HTML")


@router.callback_query(F.data == "addAdmin_prompt")
async def process_add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_super_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "<b>Yangi adminning Telegram ID sini yuboring:</b>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_admin)
    await callback.answer()


@router.message(AdminStates.add_admin)
async def process_add_admin_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID faqat raqamlardan iborat bo'lishi kerak!")
        return

    new_admin_id = int(message.text)
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO admins (user_id, added_by) VALUES (?, ?)",
                (new_admin_id, message.from_user.id)
            )
            await db.commit()
            await message.answer(f"✅ Yangi admin qo'shildi: <code>{new_admin_id}</code>", parse_mode="HTML", reply_markup=panel_kb())
        except aiosqlite.IntegrityError:
            await message.answer("❌ Bu foydalanuvchi allaqachon admin!")
    await state.clear()


@router.callback_query(F.data == "removeAdmin_prompt")
async def remove_admin_prompt(callback: CallbackQuery):
    if not await is_super_admin(callback.from_user.id):
        return
        
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as cursor:
            admins_list = await cursor.fetchall()

    if not admins_list:
        await callback.answer("O'chirish uchun adminlar yo'q!", show_alert=True)
        return

    buttons = []
    for a in admins_list:
        buttons.append([InlineKeyboardButton(text=f"🗑 {a[0]}", callback_data=f"delAdmin={a[0]}")])

    await callback.message.answer(
        "<b>O'chirish uchun adminni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delAdmin="))
async def delete_admin_callback(callback: CallbackQuery):
    if not await is_super_admin(callback.from_user.id):
        return
    admin_to_del = int(callback.data.split("=")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (admin_to_del,))
        await db.commit()
    await callback.message.edit_text(f"✅ Admin <code>{admin_to_del}</code> o'chirildi!", parse_mode="HTML")
    await callback.answer()


# ─── 📬 Post tayyorlash ───────────────────────────────────────────────────────

@router.message(F.text == "📬 Post tayyorlash")
async def start_post_creation(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "<b>📬 Post uchun rasm yoki video yuboring.</b>\n\n"
        "<i>Agar faqat matnli post bo'lsa, matnni yuboring.</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(PostStates.media)


@router.message(PostStates.media)
async def process_post_media(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(post_type="photo", media_id=message.photo[-1].file_id)
        if message.caption:
            await state.update_data(caption=message.caption)
            await ask_post_buttons(message, state)
            return
    elif message.video:
        await state.update_data(post_type="video", media_id=message.video.file_id)
        if message.caption:
            await state.update_data(caption=message.caption)
            await ask_post_buttons(message, state)
            return
    elif message.text:
        await state.update_data(post_type="text", caption=message.text)
        await ask_post_buttons(message, state)
        return
    else:
        await message.answer("❌ Noto'g'ri format. Rasm, video yoki matn yuboring.")
        return

    await message.answer("<b>Endi post uchun matn (caption) yuboring:</b>\n\n<i>Matn kerak bo'lmasa 0 yoki yo'q deb yozing.</i>", parse_mode="HTML")
    await state.set_state(PostStates.caption)


@router.message(PostStates.caption, F.text)
async def process_post_caption(message: Message, state: FSMContext):
    if message.text.lower() not in ["0", "yo'q", "yoq", "no", "-"]:
        await state.update_data(caption=message.text)
    
    await ask_post_buttons(message, state)


async def ask_post_buttons(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text FROM custom_buttons") as cursor:
            btns = await cursor.fetchall()
            
    if not btns:
        await show_post_preview(message, state)
        return

    text = "<b>🎛 Postga qaysi tugmalarni qo'shamiz?</b>\n\n"
    buttons = []
    for b in btns:
        text += f"• <code>{b[1]}</code>\n"
        buttons.append([InlineKeyboardButton(text=f"➕ {b[1]}", callback_data=f"addPBtn={b[0]}")])
        
    buttons.append([InlineKeyboardButton(text="✅ Tugatish (Tugma qo'shmaslik)", callback_data="donePBtns")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await state.update_data(selected_btns=[])
    await state.set_state(PostStates.buttons)


@router.callback_query(PostStates.buttons, F.data.startswith("addPBtn="))
async def add_btn_to_post(callback: CallbackQuery, state: FSMContext):
    btn_id = int(callback.data.split("=")[1])
    data = await state.get_data()
    selected = data.get("selected_btns", [])
    if btn_id not in selected:
        selected.append(btn_id)
        await state.update_data(selected_btns=selected)
        await callback.answer("Tugma postga qo'shildi!")
    else:
        await callback.answer("Bu tugma allaqachon qo'shilgan!")


@router.callback_query(PostStates.buttons, F.data == "donePBtns")
async def finish_post_buttons(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await show_post_preview(callback.message, state)


async def show_post_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    post_type = data.get("post_type")
    media_id = data.get("media_id")
    caption = data.get("caption", "")
    selected_btns = data.get("selected_btns", [])

    inline_kb = None
    if selected_btns:
        async with aiosqlite.connect(DB_PATH) as db:
            placeholders = ",".join("?" * len(selected_btns))
            async with db.execute(f"SELECT text, url FROM custom_buttons WHERE id IN ({placeholders})", selected_btns) as cursor:
                db_btns = await cursor.fetchall()
                
        kb_list = [[InlineKeyboardButton(text=b[0], url=b[1])] for b in db_btns]
        inline_kb = InlineKeyboardMarkup(inline_keyboard=kb_list)

    await message.answer("<b>👁 Post ko'rinishi:</b>", parse_mode="HTML")
    
    try:
        if post_type == "photo":
            await message.answer_photo(photo=media_id, caption=caption, reply_markup=inline_kb, parse_mode="HTML")
        elif post_type == "video":
            await message.answer_video(video=media_id, caption=caption, reply_markup=inline_kb, parse_mode="HTML")
        else:
            await message.answer(text=caption, reply_markup=inline_kb, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")
        return

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Barchaga yuborish", callback_data="sendPostAll")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancelPost")]
    ])
    await message.answer("<b>Postni tayyorladingiz. Barcha foydalanuvchilarga yuboramizmi?</b>", reply_markup=confirm_kb, parse_mode="HTML")
    await state.set_state(PostStates.confirm)


@router.callback_query(PostStates.confirm, F.data == "sendPostAll")
async def execute_send_post(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_type = data.get("post_type")
    media_id = data.get("media_id")
    caption = data.get("caption", "")
    selected_btns = data.get("selected_btns", [])

    inline_kb = None
    if selected_btns:
        async with aiosqlite.connect(DB_PATH) as db:
            placeholders = ",".join("?" * len(selected_btns))
            async with db.execute(f"SELECT text, url FROM custom_buttons WHERE id IN ({placeholders})", selected_btns) as cursor:
                db_btns = await cursor.fetchall()
        kb_list = [[InlineKeyboardButton(text=b[0], url=b[1])] for b in db_btns]
        inline_kb = InlineKeyboardMarkup(inline_keyboard=kb_list)

    await callback.message.edit_text("⏳ <i>Joz'natilmoqda... Bu jarayon biroz vaqt olishi mumkin.</i>", parse_mode="HTML")
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE ban='unban'") as cursor:
            users = await cursor.fetchall()

    sent = 0
    failed = 0
    for (uid,) in users:
        try:
            if post_type == "photo":
                await bot.send_photo(chat_id=uid, photo=media_id, caption=caption, reply_markup=inline_kb, parse_mode="HTML")
            elif post_type == "video":
                await bot.send_video(chat_id=uid, video=media_id, caption=caption, reply_markup=inline_kb, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=uid, text=caption, reply_markup=inline_kb, parse_mode="HTML")
            sent += 1
        except:
            failed += 1

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Post muvaffaqiyatli yuborildi!</b>\n\n"
        f"📤 Yuborildi: <b>{sent}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(PostStates.confirm, F.data == "cancelPost")
async def cancel_send_post(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ <b>Post yuborish bekor qilindi.</b>", parse_mode="HTML")
    await callback.answer()


# ─── 🎛 Tugmalar ─────────────────────────────────────────────────────────────

@router.message(F.text == "🎛 Tugmalar")
async def buttons_handler(message: Message):
    if not await is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text, url FROM custom_buttons") as cursor:
            btns = await cursor.fetchall()

    if not btns:
        text = "<b>🎛 Hozircha hech qanday tugma qo'shilmagan.</b>\n\nTugmalar 📬 Post tayyorlashda ishlatiladi."
    else:
        text = "<b>🎛 Qo'shilgan tugmalar:</b>\n\n"
        for b in btns:
            text += f"• <b>{b[1]}</b> → <code>{b[2]}</code>\n"

    action_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data="addCustomBtn")],
        [InlineKeyboardButton(text="🗑 Tugma o'chirish", callback_data="removeCustomBtn")],
    ])
    await message.answer(text, reply_markup=action_buttons, parse_mode="HTML")


@router.callback_query(F.data == "addCustomBtn")
async def add_custom_btn_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>➕ Tugma matni kiriting:</b>\n\n<i>Misol: 🌐 Bizning kanal</i>",
        parse_mode="HTML"
    )
    await state.set_state(ButtonStates.add_btn_text)
    await callback.answer()


@router.message(ButtonStates.add_btn_text)
async def process_btn_text(message: Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer(
        "<b>🔗 Tugma URL sini kiriting:</b>\n\n<i>Misol: https://t.me/kanal_nomi</i>",
        parse_mode="HTML"
    )
    await state.set_state(ButtonStates.add_btn_url)


@router.message(ButtonStates.add_btn_url)
async def process_btn_url(message: Message, state: FSMContext):
    if not message.text.startswith("http"):
        await message.answer("❌ URL noto'g'ri! https:// bilan boshlashi kerak.")
        return

    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO custom_buttons (text, url) VALUES (?, ?)",
            (data['btn_text'], message.text)
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ Tugma qo'shildi!\n\n<b>{data['btn_text']}</b> → <code>{message.text}</code>",
        reply_markup=panel_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data == "removeCustomBtn")
async def remove_custom_btn_prompt(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text, url FROM custom_buttons") as cursor:
            btns = await cursor.fetchall()

    if not btns:
        await callback.answer("Hech qanday tugma yo'q!", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(text=f"🗑 {b[1]}", callback_data=f"delCustomBtn={b[0]}")]
        for b in btns
    ]
    await callback.message.answer(
        "<b>O'chirish uchun tugmani tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delCustomBtn="))
async def delete_custom_btn(callback: CallbackQuery):
    btn_id = int(callback.data.split("=")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM custom_buttons WHERE id=?", (btn_id,))
        await db.commit()
    await callback.message.edit_text("✅ Tugma o'chirildi!")
    await callback.answer()


# ─── 📬 Post tayyorlash ───────────────────────────────────────────────────────

@router.message(F.text == "📬 Post tayyorlash")
async def post_prepare_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "<b>📬 Post tayyorlash</b>\n\n"
        "1️⃣ Rasm yoki video yuboring\n"
        "<i>(Faqat matn post bo'lsa /skip yozing)</i>",
        reply_markup=boshqarish_kb(), parse_mode="HTML"
    )
    await state.set_state(PostStates.media)


@router.message(PostStates.media, F.photo | F.video | F.document)
async def post_get_media(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(media_type="photo", media_id=message.photo[-1].file_id)
    elif message.video:
        await state.update_data(media_type="video", media_id=message.video.file_id)
    elif message.document:
        await state.update_data(media_type="document", media_id=message.document.file_id)

    await message.answer(
        "2️⃣ Post matni (caption) ni yuboring:\n<i>(/skip — matnsiz)</i>",
        parse_mode="HTML"
    )
    await state.set_state(PostStates.caption)


@router.message(PostStates.media, F.text)
async def post_skip_media(message: Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(media_type=None, media_id=None)
        await message.answer("2️⃣ Post matni (caption) ni yuboring:")
        await state.set_state(PostStates.caption)
    else:
        await message.answer("❌ Rasm, video yuboring yoki /skip yozing.")


@router.message(PostStates.caption, F.text)
async def post_get_caption(message: Message, state: FSMContext):
    caption = None if message.text == "/skip" else message.text
    await state.update_data(caption=caption)

    # Saqlangan tugmalarni ko'rsat
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text, url FROM custom_buttons") as cursor:
            saved_btns = await cursor.fetchall()

    if saved_btns:
        btn_list = "\n".join([f"• {b[1]}" for b in saved_btns])
        btns_ui = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Saqlangan tugmalarni qo'sh", callback_data="postUseSavedBtns")],
            [InlineKeyboardButton(text="✏️ Yangi tugma qo'shish", callback_data="postAddNewBtn")],
            [InlineKeyboardButton(text="🚫 Tugrumsiz yuborish", callback_data="postNoBtns")],
        ])
        await message.answer(
            f"3️⃣ Tugmalar:\n\n<b>Saqlangan tugmalar:</b>\n{btn_list}\n\nQaysi variantni tanlaysiz?",
            reply_markup=btns_ui, parse_mode="HTML"
        )
    else:
        btns_ui = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Yangi tugma qo'shish", callback_data="postAddNewBtn")],
            [InlineKeyboardButton(text="🚫 Tugrumsiz yuborish", callback_data="postNoBtns")],
        ])
        await message.answer("3️⃣ Tugmalar qo'shmoqchimisiz?", reply_markup=btns_ui)

    await state.set_state(PostStates.buttons)


@router.callback_query(PostStates.buttons, F.data == "postUseSavedBtns")
async def post_use_saved_btns(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT text, url FROM custom_buttons") as cursor:
            btns = await cursor.fetchall()
    await state.update_data(post_buttons=[[b[0], b[1]] for b in btns])
    await callback.message.answer("✅ Saqlangan tugmalar qo'shildi! Preview ko'ring:")
    await show_post_preview(callback.message, state)
    await callback.answer()


@router.callback_query(PostStates.buttons, F.data == "postAddNewBtn")
async def post_add_new_btn(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "✏️ Tugma matni va URL ni quyidagi formatda yuboring:\n\n"
        "<code>Tugma matni | https://t.me/kanal</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PostStates.buttons, F.text)
async def post_get_custom_btn(message: Message, state: FSMContext):
    if "|" not in message.text:
        await message.answer("❌ Format noto'g'ri! \n<code>Matn | URL</code> ko'rinishida yuboring.", parse_mode="HTML")
        return
    parts = message.text.split("|", 1)
    btn_text = parts[0].strip()
    btn_url = parts[1].strip()
    if not btn_url.startswith("http"):
        await message.answer("❌ URL https:// bilan boshlanishi kerak!")
        return

    data = await state.get_data()
    existing = data.get("post_buttons", [])
    existing.append([btn_text, btn_url])
    await state.update_data(post_buttons=existing)
    await message.answer(f"✅ Tugma qo'shildi: <b>{btn_text}</b>\n\nYana qo'shish uchun yuboring yoki preview ko'rish uchun /done yozing.", parse_mode="HTML")


@router.message(PostStates.buttons, F.text == "/done")
async def post_done_buttons(message: Message, state: FSMContext):
    await show_post_preview(message, state)


@router.callback_query(PostStates.buttons, F.data == "postNoBtns")
async def post_no_buttons(callback: CallbackQuery, state: FSMContext):
    await state.update_data(post_buttons=[])
    await show_post_preview(callback.message, state)
    await callback.answer()


async def show_post_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    media_type = data.get("media_type")
    media_id = data.get("media_id")
    caption = data.get("caption", "")
    post_buttons = data.get("post_buttons", [])

    markup = None
    if post_buttons:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=b[0], url=b[1])] for b in post_buttons
        ])

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Kanalga yuborish", callback_data="postSendNow")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="postCancel")],
    ])

    await message.answer("<b>👁 Post ko'rinishi:</b>", parse_mode="HTML")

    try:
        if media_type == "photo":
            await message.answer_photo(media_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        elif media_type == "video":
            await message.answer_video(media_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        elif media_type == "document":
            await message.answer_document(media_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        else:
            await message.answer(caption or "📭 Matn yo'q", reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Preview xatosi: {e}")

    await message.answer("Postni kanalga yuborasizmi?", reply_markup=confirm_kb)
    await state.set_state(PostStates.confirm)


@router.callback_query(PostStates.confirm, F.data == "postSendNow")
async def post_send_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    from config import MAIN_CHANNEL_ID
    data = await state.get_data()
    media_type = data.get("media_type")
    media_id = data.get("media_id")
    caption = data.get("caption", "")
    post_buttons = data.get("post_buttons", [])

    markup = None
    if post_buttons:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=b[0], url=b[1])] for b in post_buttons
        ])

    try:
        if media_type == "photo":
            await bot.send_photo(MAIN_CHANNEL_ID, media_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        elif media_type == "video":
            await bot.send_video(MAIN_CHANNEL_ID, media_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        elif media_type == "document":
            await bot.send_document(MAIN_CHANNEL_ID, media_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        else:
            await bot.send_message(MAIN_CHANNEL_ID, caption or ".", reply_markup=markup, parse_mode="HTML")

        await callback.message.answer("✅ Post muvaffaqiyatli kanalga yuborildi!", reply_markup=panel_kb())
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {e}\n(Bot kanalda admin ekanligini tekshiring)")

    await state.clear()
    await callback.answer()


@router.callback_query(PostStates.confirm, F.data == "postCancel")
async def post_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Post bekor qilindi.", reply_markup=panel_kb())
    await callback.answer()

