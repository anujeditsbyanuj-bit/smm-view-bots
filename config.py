import os

# ── Bot ──────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN", "8741784728:AAFLpwz7UZvEUumoxgO2I7ii8Lo-9ZSpa1o")
ADMIN_IDS        = list(map(int, os.getenv("ADMIN_IDS", "7168219724").split(",")))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "anujedits76")

# ── MongoDB ──────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Anujedit:Anujedit@cluster0.7cs2nhd.mongodb.net/?appName=Cluster0")

# ── SMM Panel ────────────────────────────────
SMM_API_URL    = os.getenv("SMM_API_URL", "https://easysmmpanel.com/api/v2")
SMM_API_KEY    = os.getenv("SMM_API_KEY", "ca6c4e5fcfdfa330be080b2600ff65b2")
SMM_SERVICE_ID = os.getenv("SMM_SERVICE_ID", "5000")   # Telegram post views service ID

# ── Channels ─────────────────────────────────
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "@log_ak_bots").split(",")
LOG_CHANNEL       = os.getenv("LOG_CHANNEL", "@log_ak_bots")

# ── Credits ──────────────────────────────────
WELCOME_BONUS = int(os.getenv("WELCOME_BONUS", "250"))
REF_BONUS     = int(os.getenv("REF_BONUS",     "500"))

# ── Limits ───────────────────────────────────
MIN_VIEW             = int(os.getenv("MIN_VIEW",             "100"))
MAX_VIEW             = int(os.getenv("MAX_VIEW",             "30000"))
MAX_PROJECTS_PER_USER = int(os.getenv("MAX_PROJECTS_PER_USER", "5"))

# ── Payment ───────────────────────────────────
# Rate: 1000 views = $1 USD = ₹20 INR
VIEWS_PER_DOLLAR    = int(os.getenv("VIEWS_PER_DOLLAR",   "1000"))
VIEWS_PER_RUPEE     = float(os.getenv("VIEWS_PER_RUPEE",  "50"))    # 1000 views = ₹20 → 50 views/₹
STARS_PER_1000      = int(os.getenv("STARS_PER_1000",     "77"))    # Telegram Stars per 1000 views

# UPI
UPI_ID              = os.getenv("UPI_ID", "971916880@ybl")
UPI_QR_IMAGE_URL    = os.getenv("UPI_QR_IMAGE_URL", "https://l.arzfun.com/oxGhB")

# PayPal
PAYPAL_LINK         = os.getenv("PAYPAL_LINK", "https://t.me/anujedits76")

# Crypto
CRYPTO_CONTACT      = os.getenv("CRYPTO_CONTACT", "anujedits76")

# Telegram Stars
STARS_ENABLED       = os.getenv("STARS_ENABLED", "true").lower() == "true"

# Welcome image file_id or URL
WELCOME_IMAGE       = os.getenv("WELCOME_IMAGE", "https://l.arzfun.com/Kf8Z5")
