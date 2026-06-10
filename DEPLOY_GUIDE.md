# 🤖 Views Bot — Deploy Guide

## 📁 Files List
| File | Kya hai |
|------|---------|
| `bot.py` | **Use `bot_updated.py` ko rename karke** — Flask integrated |
| `keep_alive.py` | Flask server (port 8080) |
| `Dockerfile` | Render/Railway/VPS ke liye |
| `requirements.txt` | **Use `requirements_updated.txt`** |
| `.env.example` | Environment variables template |

---

## ⚙️ Step 1 — Files Rename Karo
```
bot_updated.py       →  bot.py        (purana delete karo)
requirements_updated.txt → requirements.txt
```

---

## 🚀 Option A — Render.com (Free, Recommended)

### 1. GitHub pe upload karo
- GitHub account banao (free)
- New repository banao: `views-bot`
- Saari files upload karo (bot.py, keep_alive.py, Dockerfile, etc.)

### 2. Render pe deploy karo
1. [render.com](https://render.com) pe signup karo
2. **New → Web Service** click karo
3. GitHub repo connect karo
4. Settings:
   - **Runtime:** Docker
   - **Port:** 8080
5. **Environment Variables** add karo (neeche dekho)
6. **Deploy** click karo ✅

### 3. UptimeRobot se alive rakho (Free)
1. [uptimerobot.com](https://uptimerobot.com) pe signup karo
2. **New Monitor** → HTTP(s)
3. URL: `https://your-app.onrender.com/health`
4. Interval: **5 minutes**
- Ye bot ko 24/7 alive rakhega!

---

## 🔁 Option B — Replit (Free)

### 1. Replit pe project banao
1. [replit.com](https://replit.com) pe signup
2. **Create Repl** → **Python** select karo
3. Saari files upload karo

### 2. `.replit` file banao
```toml
[run]
command = "python bot.py"

[nix]
channel = "stable-23_11"
```

### 3. Environment Variables (Secrets)
Replit ke **Secrets** tab mein ye add karo:
```
BOT_TOKEN = apna_bot_token
MONGO_URI = mongodb+srv://...
SMM_API_KEY = apni_key
ADMIN_IDS = 7168219724
```

### 4. Always On (Paid) ya UptimeRobot (Free)
- **Free option:** UptimeRobot se ping karo Repl URL ko

---

## 🐳 Option C — VPS/Docker

```bash
# .env file banao
cp .env.example .env
nano .env   # apni values bharo

# Docker se chalao
docker build -t views-bot .
docker run -d --env-file .env --name views-bot views-bot

# Logs dekhne ke liye
docker logs -f views-bot
```

---

## 🔑 Environment Variables

`.env.example` ko copy karke `.env` banao aur ye fill karo:

```env
# REQUIRED — in ke bina bot nahi chalega
BOT_TOKEN=7xxxxxxx:AAxxxxxxxxxxxxxxxx    ← @BotFather se lo
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/viewsbot  ← MongoDB Atlas free
SMM_API_KEY=your_key_here               ← SMM panel se lo

# OPTIONAL — defaults theek hain
ADMIN_IDS=7168219724                    ← Apna Telegram ID
SMM_API_URL=https://easysmmpanel.com/api/v2
SMM_SERVICE_ID=4815
REQUIRED_CHANNELS=@your_channel
LOG_CHANNEL=@your_log_channel
WELCOME_BONUS=250
REF_BONUS=500
```

### MongoDB Atlas Free Setup:
1. [mongodb.com/atlas](https://mongodb.com/atlas) pe signup
2. Free M0 cluster banao
3. Database user banao
4. Network Access: `0.0.0.0/0` allow karo
5. Connection string copy karo → MONGO_URI mein paste karo

---

## ✅ Bot Test Karo

Deploy ke baad Telegram pe:
1. Bot ko `/start` karo
2. Admin commands test karo:
   - `/stats` — bot stats
   - `/addbalance YOUR_ID 1000` — balance add karo
   - `/addviews https://t.me/channel/1 100` — views add karo

---

## ❓ Common Errors

| Error | Fix |
|-------|-----|
| `BOT_TOKEN invalid` | @BotFather se naya token lo |
| `MongoDB connection failed` | MONGO_URI check karo, IP whitelist karo |
| `SMM panel error` | SMM_API_KEY aur SMM_SERVICE_ID verify karo |
| `Bot not polling` | Ek hi jagah chalao — 2 instances nahi |
