import os
import yt_dlp

DOWNLOAD_PATH = "downloads"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)


def _base_opts(proxy=None):
    opts = {
        "outtmpl": f"{DOWNLOAD_PATH}/%(title).80s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    if proxy:
        opts["proxy"] = proxy

    return opts


def download_video(url):
    proxy = get_proxy()

    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_PATH}/%(title).80s.%(ext)s",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,

        # 🔥 SEN QO‘SHADIGAN QISM
        "nocheckcertificate": True,
        "geo_bypass": True,
        "geo_bypass_country": "GB",
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    }

    if proxy:
        ydl_opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)

        if not path.endswith(".mp4"):
            path = path.rsplit(".", 1)[0] + ".mp4"

        return path


def download_audio(url):
    proxy = get_proxy()

    ydl_opts = _base_opts(proxy)
    ydl_opts.update({
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]
    })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)

        return path.rsplit(".", 1)[0] + ".mp3"


def safe_download(func, url, retries=3):
    for _ in range(retries):
        try:
            return func(url)
        except:
            continue
    return None


def handle(bot, data):
    # 🤖 BOT MODE
    if bot:
        chat_id = data.chat.id
        text = data.text.strip()

        if not text.startswith("http"):
            bot.send_message(chat_id, "❌ Link yubor")
            return

        bot.send_message(chat_id, "⏬ Yuklanmoqda...")

        # 🔥 avval video urinamiz
        video_path = safe_download(download_video, text)

        try:
            if video_path and os.path.exists(video_path):
                size = os.path.getsize(video_path) / (1024 * 1024)

                with open(video_path, "rb") as f:
                    if size <= 50:
                        bot.send_video(chat_id, f)
                    else:
                        bot.send_document(chat_id, f)

                return
        except:
            pass

        # 🎧 fallback audio
        audio_path = safe_download(download_audio, text)

        if audio_path and os.path.exists(audio_path):
            try:
                with open(audio_path, "rb") as f:
                    bot.send_audio(chat_id, f)
                return
            except:
                pass

        bot.send_message(chat_id, "❌ Yuklab bo‘lmadi")

    # 🌐 WEB MODE
    else:
        url = data.get("url")

        if not url:
            return {"error": "url required"}

        path = safe_download(download_video, url)

        if not path:
            return {"error": "download failed"}

        return {
            "file": path
        }