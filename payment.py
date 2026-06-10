"""
payment.py  —  All Recharge / Payment handlers
Import this in bot.py:  from payment import register_payment_handlers
"""

import math
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from config import (
    ADMIN_IDS, LOG_CHANNEL, SUPPORT_USERNAME,
    VIEWS_PER_DOLLAR, VIEWS_PER_RUPEE, STARS_PER_1000,
    UPI_ID, UPI_QR_IMAGE_URL, PAYPAL_LINK,
    CRYPTO_CONTACT, STARS_ENABLED,
)
from database import db

# ─── Helpers ─────────────────────────────────────────────────────────────────

def views_to_usd(views: int) -> float:
    return round(views / VIEWS_PER_DOLLAR, 2)

def views_to_inr(views: int) -> int:
    return math.ceil(views / VIEWS_PER_RUPEE)

def views_to_stars(views: int) -> int:
    return math.ceil((views / 1000) * STARS_PER_1000)

def usd_to_views(usd: float) -> int:
    return int(usd * VIEWS_PER_DOLLAR)

def inr_to_views(inr: float) -> int:
    return int(inr * VIEWS_PER_RUPEE)


# ─── State store (in-memory, keyed by user_id) ───────────────────────────────
# {user_id: {"views": int, "method": str, "payment_id": str}}
_pay_state: dict = {}


# ─── Register all handlers ────────────────────────────────────────────────────

def register_payment_handlers(bot: telebot.TeleBot):

    # ── 1. Recharge button / command ─────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text in ("💳 Recharge", "💰 Recharge"))
    @bot.message_handler(commands=["recharge"])
    def handle_recharge(message):
        uid = str(message.from_user.id)
        _pay_state.pop(uid, None)

        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("➕ 1,000",  callback_data="pkg_1000"),
            InlineKeyboardButton("➕ 5,000",  callback_data="pkg_5000"),
            InlineKeyboardButton("➕ 10,000", callback_data="pkg_10000"),
            InlineKeyboardButton("➕ 25,000", callback_data="pkg_25000"),
            InlineKeyboardButton("➕ 50,000", callback_data="pkg_50000"),
            InlineKeyboardButton("Custom ✏️", callback_data="pkg_custom"),
        )
        bot.send_message(
            message.chat.id,
            "💳 <b>ADD CREDITS</b>\n\n"
            "Credits are used for Views Bot services.\n\n"
            f"💵 Rate: <b>1,000 views = $1.00 / ₹20</b>\n\n"
            "Select a package or enter custom amount 👇",
            parse_mode="HTML",
            reply_markup=markup
        )

    # ── 2. Package selection ──────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pkg_"))
    def cb_package(call):
        uid   = str(call.from_user.id)
        pkg   = call.data[4:]

        if pkg == "custom":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(
                call.message.chat.id,
                "✏️ Enter the number of views you want to purchase\n"
                "(minimum 1,000):",
                parse_mode="HTML"
            )
            bot.register_next_step_handler(msg, _step_custom_views)
            return

        views = int(pkg)
        bot.answer_callback_query(call.id)
        _pay_state[uid] = {"views": views}
        _show_payment_methods(bot, call.message.chat.id, uid, views, edit=True, msg_id=call.message.message_id)

    def _step_custom_views(message):
        uid   = str(message.from_user.id)
        text  = message.text.strip()
        if not text.isdigit() or int(text) < 1000:
            bot.send_message(message.chat.id, "❌ Minimum 1,000 views. Try again with /recharge")
            return
        views = int(text)
        _pay_state[uid] = {"views": views}
        _show_payment_methods(bot, message.chat.id, uid, views)

    def _show_payment_methods(bot, chat_id, uid, views, edit=False, msg_id=None):
        usd   = views_to_usd(views)
        inr   = views_to_inr(views)
        stars = views_to_stars(views)

        text = (
            f"💳 <b>PAYMENT</b>\n\n"
            f"📦 View Credits: <b>{views:,}</b>\n"
            f"💵 Total Price: <b>${usd:.2f}</b> / <b>₹{inr}</b>\n\n"
            f"<b>SELECT METHOD 👇</b>"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("₿ Crypto\nUSDT, BTC, ETH, SOL", callback_data=f"pay_crypto_{views}"),
            InlineKeyboardButton("🛡 UPI (India)\nGPay, PhonePe, Paytm",  callback_data=f"pay_upi_{views}"),
            InlineKeyboardButton("P PayPal\nGlobal Cards",                callback_data=f"pay_paypal_{views}"),
        )
        if STARS_ENABLED:
            markup.add(InlineKeyboardButton(f"⭐ Telegram Stars\n{stars:,} Stars", callback_data=f"pay_stars_{views}"))
        markup.add(InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}"))
        markup.add(InlineKeyboardButton("◀️ Back", callback_data="recharge_back"))

        if edit and msg_id:
            try:
                bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML", reply_markup=markup)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data == "recharge_back")
    def cb_recharge_back(call):
        bot.answer_callback_query(call.id)
        # Re-trigger recharge menu
        handle_recharge(call.message)

    # ── 3. UPI Payment ────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_upi_"))
    def cb_pay_upi(call):
        views = int(call.data.split("_")[2])
        inr   = views_to_inr(views)
        uid   = str(call.from_user.id)
        bot.answer_callback_query(call.id)

        # Create pending payment in DB
        pay_id = db.create_payment(uid, views, amount_inr=inr, method="upi")
        _pay_state[uid] = {"views": views, "payment_id": pay_id, "method": "upi"}

        upi_link = f"upi://pay?pa={UPI_ID}&pn=ViewsBot&am={inr}&cu=INR"
        markup   = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"📲 Open UPI App • ₹{inr}", url=upi_link))
        markup.add(InlineKeyboardButton("✅ I've Paid — Enter UTR", callback_data=f"submit_upi_{pay_id}"))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_pay"))

        caption = (
            f"🛡 <b>UPI PAYMENT</b>\n\n"
            f"💰 Amount: <b>₹{inr}</b>\n"
            f"📦 Credits: <b>{views:,} views</b>\n\n"
            f"UPI ID: <code>{UPI_ID}</code>\n\n"
            f"1️⃣ Pay ₹{inr} to the UPI ID above\n"
            f"2️⃣ Note your <b>12-digit UTR number</b>\n"
            f"3️⃣ Click '✅ I've Paid' below"
        )

        if UPI_QR_IMAGE_URL:
            bot.send_photo(call.message.chat.id, UPI_QR_IMAGE_URL, caption=caption,
                           parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, caption, parse_mode="HTML", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("submit_upi_"))
    def cb_submit_upi(call):
        pay_id = call.data[len("submit_upi_"):]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "🔢 Enter your <b>12-digit UTR number</b>:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, _step_utr, pay_id)

    def _step_utr(message, pay_id):
        uid = str(message.from_user.id)
        utr = message.text.strip()
        if not utr.isdigit() or len(utr) < 10:
            bot.send_message(message.chat.id, "❌ Invalid UTR. Must be at least 10 digits. Try again or contact support.")
            return
        db.update_payment_ref(pay_id, utr)
        pay = db.get_payment(pay_id)

        bot.send_message(
            message.chat.id,
            f"✅ <b>Submitted for Verification!</b>\n\n"
            f"🔢 UTR: <code>{utr}</code>\n"
            f"📦 Credits: <b>{pay['views']:,} views</b>\n\n"
            f"⏳ Admin will verify and credit within minutes.",
            parse_mode="HTML"
        )
        _notify_admin_payment(bot, pay_id, pay, utr)

    # ── 4. PayPal Payment ─────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_paypal_"))
    def cb_pay_paypal(call):
        views = int(call.data.split("_")[2])
        usd   = views_to_usd(views)
        uid   = str(call.from_user.id)
        bot.answer_callback_query(call.id)

        pay_id = db.create_payment(uid, views, amount_usd=usd, method="paypal")
        _pay_state[uid] = {"views": views, "payment_id": pay_id, "method": "paypal"}

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"P Open PayPal • ${usd:.2f}", url=PAYPAL_LINK))
        markup.add(InlineKeyboardButton("✅ I've Paid — Enter Txn ID", callback_data=f"submit_paypal_{pay_id}"))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_pay"))

        bot.send_message(
            call.message.chat.id,
            f"P <b>PAYPAL PAYMENT</b>\n\n"
            f"💵 Amount: <b>${usd:.2f}</b>\n"
            f"📦 Credits: <b>{views:,} views</b>\n\n"
            f"PayPal link: <code>{PAYPAL_LINK}</code>\n\n"
            f"1️⃣ Send ${usd:.2f} via PayPal\n"
            f"2️⃣ Note your <b>Transaction ID</b>\n"
            f"3️⃣ Click '✅ I've Paid' below",
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("submit_paypal_"))
    def cb_submit_paypal(call):
        pay_id = call.data[len("submit_paypal_"):]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "🔢 Enter your <b>PayPal Transaction ID</b>:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, _step_paypal_txn, pay_id)

    def _step_paypal_txn(message, pay_id):
        txn = message.text.strip()
        if len(txn) < 8:
            bot.send_message(message.chat.id, "❌ Invalid Transaction ID. Try again.")
            return
        db.update_payment_ref(pay_id, txn)
        pay = db.get_payment(pay_id)

        bot.send_message(
            message.chat.id,
            f"✅ <b>Submitted for Verification!</b>\n\n"
            f"🔢 Txn ID: <code>{txn}</code>\n"
            f"📦 Credits: <b>{pay['views']:,} views</b>\n\n"
            f"⏳ Admin will verify and credit within minutes.",
            parse_mode="HTML"
        )
        _notify_admin_payment(bot, pay_id, pay, txn)

    # ── 5. Crypto ─────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_crypto_"))
    def cb_pay_crypto(call):
        views = int(call.data.split("_")[2])
        usd   = views_to_usd(views)
        bot.answer_callback_query(call.id)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{CRYPTO_CONTACT}"))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_pay"))

        bot.send_message(
            call.message.chat.id,
            f"₿ <b>CRYPTO PAYMENT</b>\n\n"
            f"💵 Amount: <b>${usd:.2f}</b>\n"
            f"📦 Credits: <b>{views:,} views</b>\n\n"
            f"Accepted: USDT, BTC, ETH, SOL\n"
            f"🎁 Crypto bonus: <b>+10%</b>\n\n"
            f"Contact @{CRYPTO_CONTACT} with your order to get wallet address.",
            parse_mode="HTML",
            reply_markup=markup
        )

    # ── 6. Telegram Stars ─────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pay_stars_"))
    def cb_pay_stars(call):
        views = int(call.data.split("_")[2])
        stars = views_to_stars(views)
        uid   = str(call.from_user.id)
        bot.answer_callback_query(call.id)

        pay_id = db.create_payment(uid, views, method="stars")
        _pay_state[uid] = {"views": views, "payment_id": pay_id}

        # Send Telegram Stars invoice
        prices = [LabeledPrice(label=f"{views:,} Views", amount=stars)]
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title="Views Bot Credits",
                description=f"{views:,} view credits for your channels",
                invoice_payload=f"stars_{pay_id}",
                provider_token="",          # empty = Telegram Stars
                currency="XTR",
                prices=prices,
                start_parameter="buy_views"
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Stars payment unavailable: {e}\nContact @{CRYPTO_CONTACT}")

    @bot.pre_checkout_query_handler(func=lambda q: True)
    def pre_checkout(query: PreCheckoutQuery):
        bot.answer_pre_checkout_query(query.id, ok=True)

    @bot.message_handler(content_types=["successful_payment"])
    def successful_stars_payment(message):
        uid     = str(message.from_user.id)
        payload = message.successful_payment.invoice_payload  # "stars_<pay_id>"
        if payload.startswith("stars_"):
            pay_id = payload[6:]
            result = db.approve_payment(pay_id)
            if result:
                bot.send_message(
                    message.chat.id,
                    f"⭐ <b>Stars Payment Successful!</b>\n\n"
                    f"📦 <b>{result['views']:,} view credits</b> have been added to your account!",
                    parse_mode="HTML"
                )
                _notify_channel_payment(bot, pay_id, result, "stars", auto_approved=True)

    # ── 7. Cancel ─────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "cancel_pay")
    def cb_cancel_pay(call):
        uid = str(call.from_user.id)
        _pay_state.pop(uid, None)
        bot.answer_callback_query(call.id, "❌ Cancelled")
        bot.send_message(call.message.chat.id, "❌ Payment cancelled.")

    # ── 8. Admin approve/reject ───────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith(("approve_pay_", "reject_pay_")))
    def cb_admin_payment_action(call):
        if call.from_user.id not in ADMIN_IDS:
            return bot.answer_callback_query(call.id, "⛔ Not admin", show_alert=True)

        action, pay_id = call.data.split("_pay_")
        if action == "approve":
            result = db.approve_payment(pay_id)
            if result:
                bot.answer_callback_query(call.id, "✅ Approved!")
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                bot.send_message(
                    call.message.chat.id,
                    f"✅ Payment <code>{pay_id}</code> approved.\n"
                    f"Credited <b>{result['views']:,}</b> views to user <code>{result['user_id']}</code>.",
                    parse_mode="HTML"
                )
                # Notify user
                try:
                    bot.send_message(
                        int(result["user_id"]),
                        f"🎉 <b>Payment Approved!</b>\n\n"
                        f"✅ <b>{result['views']:,} view credits</b> have been added to your account!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            else:
                bot.answer_callback_query(call.id, "⚠️ Already processed or not found", show_alert=True)

        elif action == "reject":
            result = db.reject_payment(pay_id)
            bot.answer_callback_query(call.id, "❌ Rejected")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, f"❌ Payment <code>{pay_id}</code> rejected.", parse_mode="HTML")
            if result:
                try:
                    bot.send_message(
                        int(result["user_id"]),
                        "❌ <b>Payment Rejected</b>\n\n"
                        "Your payment could not be verified. "
                        f"Contact @{SUPPORT_USERNAME} for help.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    # ── Admin: list pending payments ─────────────────────────────────────────

    @bot.message_handler(commands=["pending"])
    def cmd_pending(message):
        if message.from_user.id not in ADMIN_IDS:
            return
        pays = db.get_pending_payments()
        if not pays:
            return bot.reply_to(message, "✅ No pending payments.")
        for pay in pays[:10]:
            pid = str(pay["_id"])
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_pay_{pid}"),
                InlineKeyboardButton("❌ Reject",  callback_data=f"reject_pay_{pid}"),
            )
            bot.send_message(
                message.chat.id,
                f"💳 <b>Pending Payment</b>\n\n"
                f"🆔 Pay ID: <code>{pid}</code>\n"
                f"👤 User: <code>{pay['user_id']}</code>\n"
                f"📦 Views: <b>{pay['views']:,}</b>\n"
                f"💵 USD: ${pay.get('amount_usd', 0):.2f}\n"
                f"₹ INR: ₹{pay.get('amount_inr', 0)}\n"
                f"🏦 Method: <b>{pay['method'].upper()}</b>\n"
                f"🔢 Ref/UTR: <code>{pay.get('ref', 'Not submitted yet')}</code>\n"
                f"🕐 Time: {pay['created'].strftime('%d %b %H:%M UTC')}",
                parse_mode="HTML",
                reply_markup=markup
            )


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _notify_admin_payment(bot, pay_id, pay, ref):
    """Notify all admins about a new payment submission."""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_pay_{pay_id}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"reject_pay_{pay_id}"),
    )
    text = (
        f"💳 <b>New Payment Submission</b>\n\n"
        f"👤 User: <code>{pay['user_id']}</code>\n"
        f"📦 Views: <b>{pay['views']:,}</b>\n"
        f"💵 USD: ${pay.get('amount_usd', 0):.2f} | ₹{pay.get('amount_inr', 0)}\n"
        f"🏦 Method: <b>{pay['method'].upper()}</b>\n"
        f"🔢 Ref: <code>{ref}</code>\n"
        f"🆔 Pay ID: <code>{pay_id}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass
    try:
        bot.send_message(LOG_CHANNEL, text, parse_mode="HTML")
    except Exception:
        pass


def _notify_channel_payment(bot, pay_id, pay, method, auto_approved=False):
    text = (
        f"✅ <b>Payment {'Auto-Approved' if auto_approved else 'Approved'}</b>\n\n"
        f"👤 User: <code>{pay['user_id']}</code>\n"
        f"📦 Views: <b>{pay['views']:,}</b>\n"
        f"🏦 Method: <b>{method.upper()}</b>\n"
        f"🆔 Pay ID: <code>{pay_id}</code>"
    )
    try:
        bot.send_message(LOG_CHANNEL, text, parse_mode="HTML")
    except Exception:
        pass
