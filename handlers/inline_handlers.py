import aiosqlite
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultCachedPhoto,
    InlineQueryResultCachedVideo,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from config import DB_PATH, BOT_USERNAME

router = Router()


@router.inline_query()
async def inline_search(query: InlineQuery):
    search_text = query.query.strip()

    async with aiosqlite.connect(DB_PATH) as db:
        if search_text:
            async with db.execute(
                """
                SELECT id, nom, janri, rams, aniType, qismi, fandub, yili
                FROM animelar
                WHERE nom LIKE ?
                ORDER BY qidiruv DESC
                LIMIT 20
                """,
                (f"%{search_text}%",)
            ) as cursor:
                animes = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT id, nom, janri, rams, aniType, qismi, fandub, yili
                FROM animelar
                ORDER BY id DESC
                LIMIT 20
                """
            ) as cursor:
                animes = await cursor.fetchall()

    results = []
    for anime in animes:
        anime_id, nom, janri, rams, status, qismi, fandub, yili = anime
        status = status or "OnGoing"
        fandub = fandub or "Ovoz berilmagan"
        janri  = janri  or "—"
        qismi  = qismi  or "?"
        yili   = yili   or "—"

        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🎬 Ko'rish",
                url=f"https://t.me/{BOT_USERNAME}?start={anime_id}"
            )]
        ])

        caption = (
            f"🎬 <b>{nom}</b>\n"
            f"📖 {janri}\n"
            f"╭───────────\n"
            f"├ <b>Holati:</b> {status}\n"
            f"├ <b>Qismlar:</b> {qismi} ta\n"
            f"├ <b>Yil:</b> {yili}\n"
            f"├ <b>Ovoz:</b> {fandub}\n"
            f"╰───────────"
        )

        description = f"{janri} | {status} | {qismi} qism"

        # Telegram file_id bilan — CachedPhoto (rasm) yoki CachedVideo (video poster)
        try:
            result = InlineQueryResultCachedPhoto(
                id=str(anime_id),
                photo_file_id=rams,
                title=nom,
                description=description,
                caption=caption,
                reply_markup=btn,
                parse_mode="HTML",
            )
        except Exception:
            result = InlineQueryResultArticle(
                id=str(anime_id),
                title=f"🎬 {nom}",
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    parse_mode="HTML"
                ),
                reply_markup=btn,
            )

        results.append(result)

    if not results:
        results = [
            InlineQueryResultArticle(
                id="not_found",
                title="😔 Hech narsa topilmadi",
                description=f"«{search_text}» bo'yicha natija yo'q",
                input_message_content=InputTextMessageContent(
                    message_text=f"😔 <b>«{search_text}»</b> bo'yicha hech narsa topilmadi.",
                    parse_mode="HTML"
                )
            )
        ]

    await query.answer(
        results=results,
        cache_time=10,
        is_personal=True
    )
