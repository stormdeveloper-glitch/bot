import json
import aiohttp

from config import OPENAI_API_KEY, AI_MODEL


async def chat_with_ai(system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 500):
    """OpenAI Chat Completions orqali javob oladi. Xato bo'lsa None qaytaradi."""
    if not OPENAI_API_KEY:
        return None

    payload = {
        "model": AI_MODEL or "gpt-4o-mini",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
    except Exception:
        return None

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


async def support_ai_triage(user_text: str, faq_items: list, main_bot_username: str = "") -> dict | None:
    """
    Support savoliga AI javob + eskalatsiya qarorini qaytaradi:
    {"reply": "...", "escalate": true|false}
    """
    faq_lines = []
    for item in faq_items[:12]:
        # item format: (id, question, answer, order_num)
        faq_lines.append(f"Q: {item[1]}\nA: {item[2]}")
    faq_text = "\n\n".join(faq_lines) if faq_lines else "FAQ mavjud emas."

    main_bot = f"@{main_bot_username}" if main_bot_username else "asosiy bot"

    system_prompt = (
        "You are an Uzbek Telegram support assistant for anime bot users. "
        "Answer in Uzbek, concise and practical. "
        "If issue is account-specific, payment proof, VIP approval, ban, or anything that needs human action, set escalate=true. "
        "Otherwise set escalate=false. "
        "Return STRICT JSON only with keys: reply (string), escalate (boolean)."
    )
    user_prompt = (
        f"Main bot: {main_bot}\n\n"
        f"FAQ:\n{faq_text}\n\n"
        f"User message:\n{user_text}"
    )

    raw = await chat_with_ai(system_prompt, user_prompt, temperature=0.2, max_tokens=350)
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        reply = str(parsed.get("reply", "")).strip()
        escalate = bool(parsed.get("escalate", True))
        if not reply:
            return None
        return {"reply": reply, "escalate": escalate}
    except Exception:
        return None
