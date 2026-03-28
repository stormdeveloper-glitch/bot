import requests
from config import OPENAI_API_KEY

ALLOWED = {"pinterest", "downloader", "checker", "stats", "anime"}


def detect_tool_ai(text: str):
    try:
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a strict router. "
                            "Return ONLY one word from this list:\n"
                            "pinterest, downloader, checker, stats, anime.\n"
                            "Do not explain anything. No extra text."
                        )
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ]
            },
            timeout=10
        )

        data = res.json()
        tool = data["choices"][0]["message"]["content"].strip().lower()

        # 🔥 VALIDATION
        if tool in ALLOWED:
            return tool

        return None

    except Exception:
        return None