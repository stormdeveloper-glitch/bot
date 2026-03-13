<div align="center">

# 🎌 AniCloud Bot

**aiogram 3.x • Python 3.8+ • SQLite**

Anime ko'rish uchun eng qulay Telegram bot — qidirish, qismlar, VIP va ko'p narsa!

[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green?style=for-the-badge)](https://aiogram.dev)
[![License](https://img.shields.io/badge/license-MIT-orange?style=for-the-badge)](LICENSE)

</div>

---

## ✨ Xususiyatlar

| 🔎 Qidiruv | 📺 Qismlar | 👤 Foydalanuvchilar |
|---|---|---|
| Nom bo'yicha | Video qismlar | Balans tizimi |
| Janr bo'yicha | Pagination | VIP a'zolik |
| Kod bo'yicha | Yuklab olish | Referral tizimi |
| So'nggi yuklanganlar | — | Ban/Unban |

| 🗄 Admin Panel | 📢 Kanal | 📊 Statistika |
|---|---|---|
| Anime qo'shish | Obuna tekshirish | Foydalanuvchilar soni |
| Qism qo'shish | Kanal boshqarish | Animelar soni |
| Broadcast | Ko'p kanal | Qismlar soni |

---

## 🚀 O'rnatish

### 1. Loyihani klonlash
```bash
git clone https://github.com/username/anime-bot.git
cd anime-bot
```

### 2. Virtual muhit yaratish
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### 3. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 4. `.env` faylini sozlash
```bash
cp .env.example .env
```

`.env` faylini oching va quyidagilarni to'ldiring:

```env
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=your_bot_username
SUPER_ADMIN_ID=123456789
ADMIN_IDS=123456789,987654321
```

> 💡 Bot tokenini [@BotFather](https://t.me/BotFather) dan olishingiz mumkin.

### 5. Botni ishga tushirish
```bash
python main.py
```

---

## 📁 Fayl Tuzilmasi

```
anime-bot/
├── 📄 main.py               # Asosiy ishga tushirish fayli
├── ⚙️ config.py             # Sozlamalar (env o'zgaruvchilar)
├── 🗄 database.py           # SQLite ma'lumotlar bazasi
├── 🎯 states.py             # FSM holatlar
├── 🛠 utils.py              # Yordamchi funksiyalar
├── ⌨️ keyboards.py          # Tugmalar (Reply & Inline)
├── 📂 handlers/
│   ├── 👤 user_handlers.py  # Foydalanuvchi handlerlari
│   └── 🗄 admin_handlers.py # Admin handlerlari
├── 📦 requirements.txt      # Python kutubxonalar
├── 📋 .env.example          # Namuna konfiguratsiya
└── 📖 README.md
```

---

## 🗄 Ma'lumotlar Bazasi Jadvallari

| Jadval | Tavsif |
|--------|--------|
| `users` | Foydalanuvchilar (balans, status, referal) |
| `animelar` | Animelar ro'yxati (nom, janr, yil, ...) |
| `anime_datas` | Qismlar (video file_id lar) |
| `channels` | Obuna kanallar ro'yxati |
| `vip_status` | VIP foydalanuvchilar |

---

## 🚂 Railway Deploy

### 1. GitHub ga yuklang
```bash
git add .
git commit -m "Initial commit"
git push
```

### 2. Railway sozlamalari
1. [Railway.app](https://railway.app) da yangi loyiha yarating
2. GitHub repozitoriyni ulang
3. **Variables** bo'limiga `.env` dagi barcha o'zgaruvchilarni qo'shing

### 3. Doimiy xotira (Volume)
> ⚠️ Ma'lumotlar o'chmasligi uchun Volume qo'shish **MAJBURIY!**

1. Railway loyihasida **Volumes** bo'limiga o'ting
2. Yangi Volume yarating
3. **Mount Path**: `/app/data`

---

## 🤝 Hissa Qo'shish

Pull request larni kutib qolamiz! Katta o'zgarishlar uchun avval **Issue** oching.

---

<div align="center">

Made with ❤️ for anime fans 🎌

</div>