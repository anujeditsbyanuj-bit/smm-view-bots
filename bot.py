import telebot
import re
import requests
import time
import threading
import schedule
import logging
from datetime import datetime, timedelta
from telebot.types import (
    KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from config import *  # noqa
from database import db
from payment import register_payment_handlers
from keep_alive import keep_alive  # ← Flask keep-alive

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ─────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("👁 Views"), KeyboardButton("🔄 Auto Views"))
    markup.add(KeyboardButton("🗣 Referral"), KeyboardButton("👤 My Account"))
    markup.add(KeyboardButton("💰 Recharge"))
    return markup

def auto_views_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ Add Project"), KeyboardButton("📋 My Projects"))
    markup.add(KeyboardButton("🏠 Back"))
    return markup

def cancel_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("✘ Cancel"))
    return markup

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

def is_member(user_id):
    for ch in REQUIRED_CHANNELS:
        try:
            status = bot.get_chat_member(ch, user_id).status
            if status not in ('member', 'administrator', 'creator'):
                return False
        except Exception:
            return False
    return True

def is_valid_tg_link(link):
    return bool(re.match(r'^https?://t\.me/[a-zA-Z0-9_@]{3,}/\d+$', link))

def send_smm_order(link, quantity):
    """Send order to SMM panel. Returns order_id or None."""
    try:
        resp = requests.post(
            SMM_API_URL,
            data={
                'key':      SMM_API_KEY,
                'action':   'add',
                'service':  SMM_SERVICE_ID,
                'link':     link,
                'quantity': quantity,
            },
            timeout=20
        )
        data = resp.json()
        logger.info(f"SMM response: {data}")
        return data.get('order'), data.get('error')
    except Exception as e:
        logger.error(f"SMM panel error: {e}")
        return None, str(e)

def notify_channel(text):
    try:
        bot.send_message(LOG_CHANNEL, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"Log channel notify failed: {e}")

# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id   = message.from_user.id
    uid_str   = str(user_id)
    first     = message.from_user.first_name or "User"
    parts     = message.text.split()
    ref_param = None

    if len(parts) > 1:
        param = parts[1]
        if param.startswith("ref_") and param[4:].isdigit():
            ref_param = param[4:]
        elif param.isdigit():
            ref_param = param

    # Register user
    if not db.user_exists(uid_str):
        ref_by = ref_param if (ref_param and ref_param != uid_str and db.user_exists(ref_param)) else None
        db.insert_user(uid_str, first, ref_by)
        # Welcome bonus
        db.add_balance(uid_str, WELCOME_BONUS)
        bot.send_message(user_id, f"🎁 Welcome bonus: +{WELCOME_BONUS} views added!")
        # Referral bonus
        if ref_by:
            db.add_balance(ref_by, REF_BONUS)
            db.increment_refs(ref_by)
            try:
                bot.send_message(int(ref_by), f"🎉 {first} joined using your link! +{REF_BONUS} views added to your account.")
            except Exception:
                pass

    if not is_member(user_id):
        ch_list = "\n".join(f"• {c}" for c in REQUIRED_CHANNELS)
        markup = InlineKeyboardMarkup()
        for ch in REQUIRED_CHANNELS:
            markup.add(InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}"))
        markup.add(InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(
            user_id,
            f"⚠️ Join required channels first:\n{ch_list}",
            reply_markup=markup
        )
        return

    welcome_text = (
    "👑 <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴠɪᴇᴡꜱ ʙᴏᴛ ᴠɪᴘ</b> 👑\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "👁 <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴜᴛᴏᴍᴀᴛɪᴄ ᴠɪᴇᴡꜱ ꜱᴇʀᴠɪᴄᴇ</b>\n\n"
    "🚀 <b>ꜰᴇᴀᴛᴜʀᴇꜱ:</b>\n"
    "┣ ✦ ꜱᴜᴘᴘᴏʀᴛꜱ <b>ᴘᴜʙʟɪᴄ & ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀɴɴᴇʟꜱ</b>\n"
    "┣ ✦ ᴀᴜᴛᴏ ᴠɪᴇᴡꜱ ᴏɴ ᴇᴠᴇʀʏ ɴᴇᴡ ᴘᴏꜱᴛ\n"
    "┣ ✦ ᴀᴅᴊᴜꜱᴛᴀʙʟᴇ ꜱᴘᴇᴇᴅ ᴍᴏᴅᴇꜱ\n"
    "┃   • 🐢 ꜱʟᴏᴡ\n"
    "┃   • ⚡ ᴍᴇᴅɪᴜᴍ\n"
    "┃   • 🔥 ꜰᴀꜱᴛ\n"
    "┣ ✦ ꜱᴛᴀʙʟᴇ & ꜱᴇᴄᴜʀᴇ ꜱʏꜱᴛᴇᴍ\n"
    "┗ ✦ 24/7 ᴀᴄᴛɪᴠᴇ ꜱᴇʀᴠɪᴄᴇ\n\n"
    "💎 <b>ᴇxᴘᴇʀɪᴇɴᴄᴇ ᴘʀᴇᴍɪᴜᴍ Qᴜᴀʟɪᴛʏ ᴠɪᴇᴡꜱ</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚜️ <b>ᴘᴏᴡᴇʀᴇᴅ ʙʏ @AnujEdits76</b> ⚜️"
)
    if WELCOME_IMAGE:
        try:
            bot.send_photo(user_id, WELCOME_IMAGE, caption=welcome_text, parse_mode="HTML", reply_markup=main_menu())
        except Exception:
            bot.send_message(user_id, welcome_text, parse_mode="HTML", reply_markup=main_menu())
    else:
        bot.send_message(user_id, welcome_text, parse_mode="HTML", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check_join(call):
    if is_member(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Verified!")
        bot.send_message(call.from_user.id, "✅ Access granted!", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined yet!", show_alert=True)

# ─────────────────────────────────────────────
#  ADMIN COMMANDS
# ─────────────────────────────────────────────

@bot.message_handler(commands=['addviews'])
def cmd_addviews(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    parts = message.text.strip().split()
    if len(parts) < 3:
        return bot.reply_to(
            message,
            "❌ Usage:\n"
            "<code>/addviews POST_LINK AMOUNT</code>\n"
            "<code>/addviews POST_LINK AMOUNT USER_ID</code>\n\n"
            "Example:\n"
            "<code>/addviews https://t.me/mychannel/42 5000</code>",
            parse_mode="HTML"
        )

    link       = parts[1]
    amount_str = parts[2]
    target_uid = parts[3] if len(parts) >= 4 else "admin"

    if not amount_str.isdigit() or int(amount_str) < 1:
        return bot.reply_to(message, "❌ Amount must be a positive integer.")

    if not is_valid_tg_link(link):
        return bot.reply_to(
            message,
            "❌ Invalid Telegram post link.\n"
            "Format: <code>https://t.me/channel/postid</code>",
            parse_mode="HTML"
        )

    amount = int(amount_str)
    bot.reply_to(
        message,
        f"⏳ Placing order of <b>{amount:,}</b> views...\n🔗 {link}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    order_id, error = send_smm_order(link, amount)

    if order_id:
        bot.send_message(
            message.chat.id,
            f"✅ <b>Order Placed Successfully!</b>\n\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"🔗 Link: {link}\n"
            f"👀 Views: <b>{amount:,}</b>\n"
            f"⚡ Status: Processing...",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        db.log_admin_order(target_uid, link, amount, order_id, message.from_user.id)
        notify_channel(
            f"📢 <b>Admin Views Order</b>\n"
            f"Admin: <code>{message.from_user.id}</code>\n"
            f"🔗 {link}\n"
            f"👀 {amount:,} views | Order ID: <code>{order_id}</code>"
        )
    else:
        bot.send_message(
            message.chat.id,
            f"❌ Order failed!\nError: <code>{error}</code>",
            parse_mode="HTML"
        )


@bot.message_handler(commands=['addbalance'])
def cmd_addbalance(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    parts = message.text.strip().split()
    if len(parts) < 3:
        return bot.reply_to(message, "❌ Usage: <code>/addbalance USER_ID AMOUNT</code>", parse_mode="HTML")

    target_uid = parts[1]
    amount_str = parts[2]

    if not amount_str.isdigit():
        return bot.reply_to(message, "❌ Amount must be a positive integer.")

    amount = int(amount_str)
    if not db.user_exists(target_uid):
        return bot.reply_to(message, f"❌ User <code>{target_uid}</code> not found.", parse_mode="HTML")

    db.add_balance(target_uid, amount)
    new_bal = db.get_balance(target_uid)

    bot.reply_to(
        message,
        f"✅ Added <b>{amount:,}</b> credits to <code>{target_uid}</code>\n"
        f"New balance: <b>{new_bal:,}</b> views",
        parse_mode="HTML"
    )
    try:
        bot.send_message(int(target_uid), f"🎁 Admin added <b>{amount:,}</b> views to your account!\n💰 New balance: <b>{new_bal:,}</b> views", parse_mode="HTML")
    except Exception:
        pass


@bot.message_handler(commands=['removebalance'])
def cmd_removebalance(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    parts = message.text.strip().split()
    if len(parts) < 3:
        return bot.reply_to(message, "❌ Usage: <code>/removebalance USER_ID AMOUNT</code>", parse_mode="HTML")

    target_uid = parts[1]
    amount_str = parts[2]

    if not amount_str.isdigit():
        return bot.reply_to(message, "❌ Amount must be a positive integer.")

    if not db.user_exists(target_uid):
        return bot.reply_to(message, f"❌ User <code>{target_uid}</code> not found.", parse_mode="HTML")

    amount = int(amount_str)
    db.cut_balance(target_uid, amount)
    new_bal = db.get_balance(target_uid)

    bot.reply_to(
        message,
        f"✅ Removed <b>{amount:,}</b> credits from <code>{target_uid}</code>\n"
        f"New balance: <b>{new_bal:,}</b> views",
        parse_mode="HTML"
    )


@bot.message_handler(commands=['addsubscription'])
def cmd_addsubscription(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    parts = message.text.strip().split()
    if len(parts) < 4:
        return bot.reply_to(
            message,
            "❌ Usage: <code>/addsubscription USER_ID DAILY_AMOUNT DAYS</code>\n"
            "Example: <code>/addsubscription 123456789 100 30</code>",
            parse_mode="HTML"
        )

    target_uid  = parts[1]
    daily_str   = parts[2]
    days_str    = parts[3]

    if not (daily_str.isdigit() and days_str.isdigit()):
        return bot.reply_to(message, "❌ DAILY_AMOUNT and DAYS must be positive integers.")

    if not db.user_exists(target_uid):
        return bot.reply_to(message, f"❌ User <code>{target_uid}</code> not found.", parse_mode="HTML")

    daily_amount = int(daily_str)
    days         = int(days_str)
    expiry       = datetime.utcnow() + timedelta(days=days)

    db.set_subscription(target_uid, daily_amount, expiry)

    bot.reply_to(
        message,
        f"✅ Subscription activated!\n\n"
        f"👤 User: <code>{target_uid}</code>\n"
        f"📅 Duration: <b>{days} days</b>\n"
        f"💰 Daily credit: <b>{daily_amount:,} views/day</b>\n"
        f"⏰ Expires: <b>{expiry.strftime('%Y-%m-%d')}</b>",
        parse_mode="HTML"
    )
    try:
        bot.send_message(
            int(target_uid),
            f"🎉 You received a <b>{days}-day subscription</b>!\n"
            f"💰 <b>{daily_amount:,} views</b> will be credited to your account every day.\n"
            f"⏰ Expires: <b>{expiry.strftime('%Y-%m-%d')}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@bot.message_handler(commands=['removesubscription'])
def cmd_removesubscription(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    parts = message.text.strip().split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Usage: <code>/removesubscription USER_ID</code>", parse_mode="HTML")

    target_uid = parts[1]
    if not db.user_exists(target_uid):
        return bot.reply_to(message, f"❌ User <code>{target_uid}</code> not found.", parse_mode="HTML")

    db.cancel_subscription(target_uid)
    bot.reply_to(message, f"✅ Subscription cancelled for <code>{target_uid}</code>.", parse_mode="HTML")
    try:
        bot.send_message(int(target_uid), "ℹ️ Your subscription has been cancelled by admin.")
    except Exception:
        pass


@bot.message_handler(commands=['userinfo'])
def cmd_userinfo(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    parts = message.text.strip().split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Usage: <code>/userinfo USER_ID</code>", parse_mode="HTML")

    uid = parts[1]
    user = db.get_user(uid)
    if not user:
        return bot.reply_to(message, f"❌ User <code>{uid}</code> not found.", parse_mode="HTML")

    sub = user.get('subscription', {})
    sub_text = "None"
    if sub and sub.get('active'):
        expiry = sub.get('expiry')
        if expiry and expiry > datetime.utcnow():
            sub_text = f"{sub.get('daily_amount', 0):,}/day until {expiry.strftime('%Y-%m-%d')}"
        else:
            sub_text = "Expired"

    bot.reply_to(
        message,
        f"👤 <b>User Info</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"📛 Name: {user.get('name', 'N/A')}\n"
        f"💰 Balance: <b>{int(user.get('balance', 0)):,}</b> views\n"
        f"🗣 Referrals: {user.get('total_refs', 0)}\n"
        f"📋 Auto Projects: {db.count_auto_projects(uid)}\n"
        f"🎟 Subscription: {sub_text}\n"
        f"📅 Joined: {user.get('joined', 'N/A')}",
        parse_mode="HTML"
    )


@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    text = message.text[len('/broadcast'):].strip()
    if not text:
        return bot.reply_to(message, "❌ Usage: <code>/broadcast Your message</code>", parse_mode="HTML")

    users = db.get_all_user_ids()
    sent = 0
    failed = 0
    for uid in users:
        try:
            bot.send_message(int(uid), text, parse_mode="HTML")
            sent += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    bot.reply_to(message, f"📢 Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}")


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Unauthorized.")

    total_users    = db.count_users()
    total_projects = db.count_all_auto_projects()
    total_orders   = db.count_orders()

    bot.reply_to(
        message,
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"📋 Auto Projects: <b>{total_projects}</b>\n"
        f"📦 Total Orders: <b>{total_orders}</b>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
#  MAIN MENU HANDLERS
# ─────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == "👤 My Account")
def handle_my_account(message):
    uid = str(message.from_user.id)
    bot_username = bot.get_me().username
    user = db.get_user(uid)
    if not user:
        return bot.reply_to(message, "Please /start first.")

    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    balance  = int(user.get('balance', 0))
    refs     = user.get('total_refs', 0)
    projects = db.count_auto_projects(uid)

    sub      = user.get('subscription', {})
    sub_text = "❌ None"
    if sub and sub.get('active'):
        expiry = sub.get('expiry')
        if expiry and expiry > datetime.utcnow():
            sub_text = f"✅ {sub.get('daily_amount', 0):,}/day (expires {expiry.strftime('%d %b %Y')})"
        else:
            sub_text = "⚠️ Expired"

    bot.reply_to(
        message,
        f"👤 <b>MY ACCOUNT</b>\n\n"
        f"📛 Name: <b>{user.get('name', 'N/A')}</b>\n"
        f"🆔 User ID: <code>{uid}</code>\n\n"
        f"💰 Credits: <b>{balance:,}</b> views\n"
        f"🗣 Referrals: <b>{refs}</b>\n"
        f"📋 Auto Projects: <b>{projects}</b>\n"
        f"🎟 Subscription: {sub_text}\n\n"
        f"🔗 Referral Link:\n<code>{ref_link}</code>",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🗣 Referral")
def handle_invite(message):
    uid = str(message.from_user.id)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    user     = db.get_user(uid)
    refs     = user.get('total_refs', 0) if user else 0

    bot.reply_to(
        message,
        f"⭐️ <b>REFERRAL PROGRAM</b>\n\n"
        f"Invite friends and earn <b>{REF_BONUS} credits</b> per referral!\n\n"
        f"🔗 Your Referral Link:\n<code>{ref_link}</code>\n\n"
        f"👥 Total Referrals: <b>{refs}</b>\n"
        f"💰 Credits Earned: <b>{refs * REF_BONUS:,}</b>",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: m.text in ("💳 Pricing", "💰 Recharge"))
def handle_pricing(message):
    uid = str(message.from_user.id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{SUPPORT_USERNAME}"))

    bot.reply_to(
        message,
        f"<b>💎 PRICING</b>\n\n"
        f"<b>📦 Packages:</b>\n"
        f"➊ 75K views — $5 (0.07$/K)\n"
        f"➋ 170K views — $10 (0.06$/K)\n"
        f"➌ 400K views — $20 (0.05$/K)\n"
        f"➍ 750K views — $30 (0.04$/K)\n"
        f"➎ 1700K views — $50 (0.03$/K)\n"
        f"➏ 5000K views — $100 (0.02$/K)\n\n"
        f"💳 Payment: USDT, Bitcoin, Paytm, PayPal\n"
        f"🎁 Crypto bonus: 10%\n\n"
        f"🆔 Your ID: <code>{uid}</code>\n"
        f"📩 Contact: @{SUPPORT_USERNAME}",
        parse_mode="HTML",
        reply_markup=markup
    )


# ─────────────────────────────────────────────
#  ORDER VIEWS (manual)
# ─────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == "👁 Views")
def handle_order_views(message):
    uid  = str(message.from_user.id)
    user = db.get_user(uid)
    bal  = int(user.get('balance', 0)) if user else 0

    bot.reply_to(
        message,
        f"👁 <b>Order Views</b>\n\n"
        f"Enter number of views ({MIN_VIEW:,} – {MAX_VIEW:,}):\n\n"
        f"💰 Your balance: <b>{bal:,}</b> views",
        parse_mode="HTML",
        reply_markup=cancel_markup()
    )
    bot.register_next_step_handler(message, step_view_amount)


def step_view_amount(message):
    if message.text == "✘ Cancel":
        return bot.reply_to(message, "❌ Cancelled.", reply_markup=main_menu())

    uid    = str(message.from_user.id)
    amount = message.text.strip()
    user   = db.get_user(uid)
    bal    = int(user.get('balance', 0)) if user else 0

    if not amount.isdigit():
        bot.send_message(message.chat.id, "📛 Enter a valid number.", reply_markup=main_menu())
        return
    amount = int(amount)
    if amount < MIN_VIEW:
        bot.send_message(message.chat.id, f"❌ Minimum is {MIN_VIEW:,} views.", reply_markup=main_menu())
        return
    if amount > MAX_VIEW:
        bot.send_message(message.chat.id, f"❌ Maximum is {MAX_VIEW:,} views.", reply_markup=main_menu())
        return
    if amount > bal:
        bot.send_message(message.chat.id, f"❌ Insufficient balance. You have {bal:,} views.", reply_markup=main_menu())
        return

    bot.send_message(message.chat.id, "🔗 Now send the Telegram post link:", reply_markup=cancel_markup())
    bot.register_next_step_handler(message, step_view_link, amount)


def step_view_link(message, amount):
    if message.text == "✘ Cancel":
        return bot.reply_to(message, "❌ Cancelled.", reply_markup=main_menu())

    uid  = str(message.from_user.id)
    link = message.text.strip()

    if not is_valid_tg_link(link):
        bot.send_message(message.chat.id, "❌ Invalid link. Must be like: https://t.me/channel/123", reply_markup=main_menu())
        return

    bot.send_message(message.chat.id, "⏳ Placing your order...")
    order_id, error = send_smm_order(link, amount)

    if order_id:
        db.cut_balance(uid, amount)
        db.log_order(uid, link, amount, order_id)
        bot.send_message(
            message.chat.id,
            f"✅ <b>Order Submitted!</b>\n\n"
            f"🆔 Order ID: <code>{order_id}</code>\n"
            f"🔗 Link: {link}\n"
            f"👀 Views: <b>{amount:,}</b>\n"
            f"💰 Balance left: <b>{int(db.get_balance(uid)):,}</b>",
            parse_mode="HTML",
            reply_markup=main_menu(),
            disable_web_page_preview=True
        )
        notify_channel(
            f"📦 <b>New Order</b>\n"
            f"👤 User: <code>{uid}</code>\n"
            f"🔗 {link}\n"
            f"👀 {amount:,} views | ID: <code>{order_id}</code>"
        )
    else:
        bot.send_message(
            message.chat.id,
            f"❌ Order failed. Please try again.\nError: <code>{error}</code>",
            parse_mode="HTML",
            reply_markup=main_menu()
        )


# ─────────────────────────────────────────────
#  AUTO VIEWS
# ─────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text == "🔄 Auto Views")
def handle_auto_views(message):
    bot.reply_to(
        message,
        "🔄 <b>AUTO VIEWS</b>\n\n"
        "Automatically send views to your channel on every new post.\n\n"
        "ℹ️ Make sure this bot is an <b>admin</b> of your channel first!",
        parse_mode="HTML",
        reply_markup=auto_views_menu()
    )


@bot.message_handler(func=lambda m: m.text == "📋 My Projects")
def handle_my_projects(message):
    uid      = str(message.from_user.id)
    projects = db.get_auto_projects(uid)

    if not projects:
        return bot.reply_to(
            message,
            "📋 <b>MY PROJECTS</b>\n\nNo projects found. Click '➕ Add Project' to create one.",
            parse_mode="HTML",
            reply_markup=auto_views_menu()
        )

    text = "📋 <b>MY PROJECTS</b>\n\n"
    for i, p in enumerate(projects, 1):
        status = "✅ Active" if p.get('active') else "⏸ Paused"
        text += (
            f"<b>{i}. {p.get('channel', 'N/A')}</b>\n"
            f"   👀 Views/post: {p.get('views_per_post', 0):,}\n"
            f"   📊 Status: {status}\n\n"
        )

    markup = InlineKeyboardMarkup()
    for p in projects:
        pid = str(p['_id'])
        ch  = p.get('channel', 'channel')
        row = []
        if p.get('active'):
            row.append(InlineKeyboardButton(f"⏸ Pause {ch}", callback_data=f"pause_proj_{pid}"))
        else:
            row.append(InlineKeyboardButton(f"▶️ Resume {ch}", callback_data=f"resume_proj_{pid}"))
        row.append(InlineKeyboardButton(f"🗑 Delete {ch}", callback_data=f"del_proj_{pid}"))
        markup.add(*row)

    bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith(("pause_proj_", "resume_proj_", "del_proj_")))
def cb_project_action(call):
    uid  = str(call.from_user.id)
    data = call.data
    pid  = data.split("_")[-1]

    if data.startswith("del_proj_"):
        db.delete_auto_project(pid, uid)
        bot.answer_callback_query(call.id, "🗑 Project deleted.")
        bot.edit_message_text("🗑 Project deleted.", call.message.chat.id, call.message.message_id)
    elif data.startswith("pause_proj_"):
        db.toggle_auto_project(pid, uid, active=False)
        bot.answer_callback_query(call.id, "⏸ Project paused.")
        bot.edit_message_text("⏸ Project paused.", call.message.chat.id, call.message.message_id)
    elif data.startswith("resume_proj_"):
        db.toggle_auto_project(pid, uid, active=True)
        bot.answer_callback_query(call.id, "▶️ Project resumed.")
        bot.edit_message_text("▶️ Project resumed.", call.message.chat.id, call.message.message_id)


@bot.message_handler(func=lambda m: m.text == "➕ Add Project")
def handle_add_project(message):
    uid      = str(message.from_user.id)
    projects = db.get_auto_projects(uid)
    user     = db.get_user(uid)
    bal      = int(user.get('balance', 0)) if user else 0

    if len(projects) >= MAX_PROJECTS_PER_USER:
        return bot.reply_to(message, f"❌ Maximum {MAX_PROJECTS_PER_USER} projects allowed per user.", reply_markup=auto_views_menu())

    bot.reply_to(
        message,
        "➕ <b>ADD AUTO VIEWS PROJECT</b>\n\n"
        "Send the <b>views count</b> you want per post:\n\n"
        f"💰 Your balance: <b>{bal:,}</b> views\n"
        f"📌 Min: {MIN_VIEW:,} | Max: {MAX_VIEW:,}",
        parse_mode="HTML",
        reply_markup=cancel_markup()
    )
    bot.register_next_step_handler(message, step_proj_views)


def step_proj_views(message):
    if message.text == "✘ Cancel":
        return bot.reply_to(message, "❌ Cancelled.", reply_markup=auto_views_menu())

    views_str = message.text.strip()
    if not views_str.isdigit():
        return bot.reply_to(message, "❌ Enter a valid number.", reply_markup=auto_views_menu())

    views = int(views_str)
    if views < MIN_VIEW or views > MAX_VIEW:
        return bot.reply_to(message, f"❌ Views must be between {MIN_VIEW:,} and {MAX_VIEW:,}.", reply_markup=auto_views_menu())

    bot.send_message(
        message.chat.id,
        "📢 Now send your <b>channel username</b> (e.g. @mychannel):",
        parse_mode="HTML",
        reply_markup=cancel_markup()
    )
    bot.register_next_step_handler(message, step_proj_channel, views)


def step_proj_channel(message, views):
    if message.text == "✘ Cancel":
        return bot.reply_to(message, "❌ Cancelled.", reply_markup=auto_views_menu())

    uid     = str(message.from_user.id)
    channel = message.text.strip()
    if not channel.startswith("@"):
        channel = "@" + channel

    try:
        member = bot.get_chat_member(channel, bot.get_me().id)
        if member.status not in ('administrator', 'creator'):
            raise Exception("Not admin")
    except Exception:
        bot.send_message(
            message.chat.id,
            f"❌ Bot is not an admin of {channel}.\n"
            f"Please add @{bot.get_me().username} as admin first, then try again.",
            reply_markup=auto_views_menu()
        )
        return

    db.add_auto_project(uid, channel, views)
    bot.send_message(
        message.chat.id,
        f"✅ <b>Auto Views Project Added!</b>\n\n"
        f"📢 Channel: <b>{channel}</b>\n"
        f"👀 Views per post: <b>{views:,}</b>\n\n"
        f"Now every new post in {channel} will automatically get <b>{views:,} views</b>!",
        parse_mode="HTML",
        reply_markup=auto_views_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🏠 Back")
def handle_back(message):
    bot.reply_to(message, "🏠 Main menu:", reply_markup=main_menu())


# ─────────────────────────────────────────────
#  CHANNEL POST LISTENER (Auto Views)
# ─────────────────────────────────────────────

@bot.channel_post_handler(func=lambda m: True)
def handle_channel_post(message):
    try:
        chat_username = f"@{message.chat.username}" if message.chat.username else None
        if not chat_username:
            return

        projects = db.get_active_projects_for_channel(chat_username)
        for proj in projects:
            uid       = proj['user_id']
            views     = proj['views_per_post']
            post_link = f"https://t.me/{message.chat.username}/{message.message_id}"

            user = db.get_user(uid)
            bal  = int(user.get('balance', 0)) if user else 0

            if bal < views:
                db.toggle_auto_project(str(proj['_id']), uid, active=False)
                try:
                    bot.send_message(
                        int(uid),
                        f"⚠️ Auto Views paused for {chat_username}!\n"
                        f"❌ Insufficient balance ({bal:,} < {views:,} views).\n"
                        f"Please recharge and resume the project.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                continue

            order_id, error = send_smm_order(post_link, views)
            if order_id:
                db.cut_balance(uid, views)
                db.log_order(uid, post_link, views, order_id, auto=True)
                logger.info(f"Auto view order placed: {order_id} for {post_link}")
            else:
                logger.error(f"Auto view order failed for {post_link}: {error}")
    except Exception as e:
        logger.error(f"Channel post handler error: {e}")


# ─────────────────────────────────────────────
#  DAILY SUBSCRIPTION CRON
# ─────────────────────────────────────────────

def run_daily_subscription_credits():
    logger.info("Running daily subscription credits job...")
    users = db.get_subscribed_users()
    count = 0
    for user in users:
        uid  = str(user['user_id'])
        sub  = user.get('subscription', {})
        if not sub or not sub.get('active'):
            continue
        expiry = sub.get('expiry')
        if expiry and expiry < datetime.utcnow():
            db.cancel_subscription(uid)
            try:
                bot.send_message(int(uid), "⚠️ Your subscription has expired. Recharge to continue.")
            except Exception:
                pass
            continue
        daily = sub.get('daily_amount', 0)
        if daily > 0:
            db.add_balance(uid, daily)
            count += 1
            try:
                bot.send_message(int(uid), f"💰 Daily subscription credit: +<b>{daily:,}</b> views added!", parse_mode="HTML")
            except Exception:
                pass
    logger.info(f"Daily credits done — credited {count} users.")


def scheduler_thread():
    schedule.every().day.at("00:00").do(run_daily_subscription_credits)
    while True:
        schedule.run_pending()
        time.sleep(60)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    # Start Flask keep-alive server (for Replit/Render)
    keep_alive()
    logger.info("Keep-alive server started on port 8080.")

    # Register payment handlers
    register_payment_handlers(bot)
    logger.info("Payment handlers registered.")

    # Start scheduler in background
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()
    logger.info("Scheduler started.")

    while True:
        try:
            logger.info("Bot started polling...")
            bot.polling(
                non_stop=True,
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30,
                allowed_updates=["message", "callback_query", "channel_post"]
            )
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(15)
