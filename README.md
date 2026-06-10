# Views Bot ⚡

Telegram Views Bot with MongoDB, Auto Views, Payment System & Admin Controls.

## Files
- `bot.py` — Main bot (all handlers)
- `payment.py` — Recharge/payment system
- `database.py` — MongoDB wrapper
- `config.py` — All settings via env vars
- `.env.example` — Copy to `.env` and fill values

## Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Configure .env
```
BOT_TOKEN=your_bot_token
ADMIN_IDS=your_telegram_id
MONGO_URI=mongodb+srv://...
SMM_API_KEY=your_smm_key
UPI_ID=your_upi_id
PAYPAL_LINK=https://paypal.me/yourlink
```

### 3. Run
```
python bot.py
```

## Admin Commands
| Command | Usage | Description |
|---------|-------|-------------|
| `/addviews` | `/addviews https://t.me/ch/1 5000` | Send views to any post directly |
| `/addbalance` | `/addbalance USER_ID 5000` | Add credits to user |
| `/removebalance` | `/removebalance USER_ID 1000` | Remove credits from user |
| `/addsubscription` | `/addsubscription USER_ID 100 30` | Daily 100 views for 30 days |
| `/removesubscription` | `/removesubscription USER_ID` | Cancel subscription |
| `/userinfo` | `/userinfo USER_ID` | View user details |
| `/pending` | `/pending` | List pending payments |
| `/broadcast` | `/broadcast message` | Send message to all users |
| `/stats` | `/stats` | Bot statistics |

## /addviews Usage
```
/addviews https://t.me/channel/42 5000
/addviews https://t.me/channel/42 5000 USER_ID   ← optional user_id for log
```
No user balance used. Views go directly to the post via SMM panel.

## Payment Methods
- UPI (India) — UTR verification by admin
- PayPal — Transaction ID verification by admin
- Crypto — Contact admin
- Telegram Stars — Auto approved instantly

## Replit Setup
Add all env vars in Secrets tab, run `python bot.py`.
