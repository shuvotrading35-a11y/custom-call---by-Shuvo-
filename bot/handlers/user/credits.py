"""
bot/handlers/user/credits.py
Credit purchase flow: package selection → payment method → submit TrxID
"""

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config.constants import (
    CONVERSATION_TIMEOUT_SECONDS,
    PAYMENT_SELECT_METHOD,
    PAYMENT_SELECT_PACKAGE,
    PAYMENT_SUBMIT_TRXID,
    PAYMENT_UPLOAD_SCREENSHOT,
)
from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import CreditPackage, Payment
from bot.utils.formatters import payment_instructions_message, payment_submitted_message
from bot.utils.keyboards import (
    cancel_inline_keyboard,
    credit_packages_keyboard,
    main_menu_keyboard,
    payment_method_keyboard,
)

logger = logging.getLogger(__name__)

_PKG_ID  = "selected_pkg_id"
_METHOD  = "selected_method"
_AMOUNT  = "selected_amount"
_CREDITS = "selected_credits"


# ── Step 1: Show packages ─────────────────────────────────────────────────────
async def show_packages(update: Update, context: CallbackContext) -> int:
    async with get_session() as db:
        result = await db.execute(
            select(CreditPackage).where(CreditPackage.is_active == True).order_by(CreditPackage.sort_order)
        )
        packages = result.scalars().all()

    if not packages:
        # Fallback hardcoded packages if DB is empty
        await update.message.reply_text(
            "❌ এই মুহূর্তে কোনো প্যাকেজ নেই। পরে চেষ্টা করুন।",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "💰 *Credits কিনুন*\n\nএকটি প্যাকেজ বেছে নিন:",
        parse_mode="Markdown",
        reply_markup=credit_packages_keyboard(packages),
    )
    return PAYMENT_SELECT_PACKAGE


# ── Callback: Package selected ────────────────────────────────────────────────
async def package_selected(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data  # "pkg:123" or "pkg:cancel"

    if data == "pkg:cancel":
        await query.edit_message_text("❌ বাতিল হয়েছে।")
        return ConversationHandler.END

    pkg_id = int(data.split(":")[1])

    async with get_session() as db:
        result = await db.execute(select(CreditPackage).where(CreditPackage.id == pkg_id))
        pkg = result.scalar_one_or_none()

    if not pkg:
        await query.edit_message_text("❌ প্যাকেজ পাওয়া যায়নি।")
        return ConversationHandler.END

    context.user_data[_PKG_ID]  = pkg.id
    context.user_data[_AMOUNT]  = pkg.price_bdt
    context.user_data[_CREDITS] = pkg.credits + pkg.bonus

    await query.edit_message_text(
        f"✅ প্যাকেজ: *{pkg.name}* — ৳{pkg.price_bdt} ({context.user_data[_CREDITS]} Credits)\n\n"
        "💳 *পেমেন্ট পদ্ধতি বেছে নিন:*",
        
    )
    await query.message.reply_text(
        "পেমেন্ট পদ্ধতি বেছে নিন 👇",
        reply_markup=payment_method_keyboard(),
    )
    return PAYMENT_SELECT_METHOD


# ── Step 2: Payment method ────────────────────────────────────────────────────
async def payment_method_selected(update: Update, context: CallbackContext) -> int:
    text = update.message.text

    method_map = {
        "💚 bKash":  ("bkash",  settings.BKASH_MERCHANT_NUMBER),
        "🟠 Nagad":  ("nagad",  settings.NAGAD_MERCHANT_NUMBER),
        "🟣 Rocket": ("rocket", settings.ROCKET_MERCHANT_NUMBER),
    }

    if text == "⬅️ Back":
        return await show_packages(update, context)

    if text not in method_map:
        await update.message.reply_text("একটি পেমেন্ট পদ্ধতি বেছে নিন:")
        return PAYMENT_SELECT_METHOD

    method, merchant_num = method_map[text]
    context.user_data[_METHOD] = method

    await update.message.reply_text(
        payment_instructions_message(
            method=method,
            merchant_number=merchant_num,
            amount=context.user_data[_AMOUNT],
            credits=context.user_data[_CREDITS],
        ),
        parse_mode="Markdown",
        reply_markup=cancel_inline_keyboard("pay:cancel"),
    )
    await update.message.reply_text(
        "📄 Transaction ID (TrxID) টাইপ করুন:"
    )
    return PAYMENT_SUBMIT_TRXID


# ── Step 3: TrxID submission ──────────────────────────────────────────────────
async def receive_trxid(update: Update, context: CallbackContext) -> int:
    trx_id = update.message.text.strip()

    if not trx_id or len(trx_id) < 4:
        await update.message.reply_text("❌ সঠিক TrxID দিন:")
        return PAYMENT_SUBMIT_TRXID

    uid = update.effective_user.id

    async with get_session() as db:
        payment = Payment(
            user_id    = uid,
            package_id = context.user_data.get(_PKG_ID),
            method     = context.user_data[_METHOD],
            amount_bdt = context.user_data[_AMOUNT],
            credits    = context.user_data[_CREDITS],
            trx_id     = trx_id,
            status     = "pending",
            merchant_number = (
                settings.BKASH_MERCHANT_NUMBER
                if context.user_data[_METHOD] == "bkash"
                else settings.NAGAD_MERCHANT_NUMBER
                if context.user_data[_METHOD] == "nagad"
                else settings.ROCKET_MERCHANT_NUMBER
            ),
        )
        db.add(payment)
        await db.flush()
        payment_id = payment.id

    # Notify admins
    await _notify_admins_payment(context, uid, trx_id, context.user_data, payment_id)

    await update.message.reply_text(
        payment_submitted_message(
            trx_id  = trx_id,
            amount  = context.user_data[_AMOUNT],
            credits = context.user_data[_CREDITS],
        ),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_payment(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer("বাতিল হয়েছে")
        await update.callback_query.edit_message_text("❌ পেমেন্ট বাতিল।")
    else:
        await update.message.reply_text("❌ পেমেন্ট বাতিল।", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def _notify_admins_payment(
    context: CallbackContext, user_id: int, trx_id: str, data: dict, payment_id: int
) -> None:
    msg = (
        "🔔 *নতুন পেমেন্ট সাবমিট!*\n\n"
        f"👤 User: `{user_id}`\n"
        f"💳 Method: {data.get(_METHOD, '').title()}\n"
        f"💰 Amount: ৳{data.get(_AMOUNT)}\n"
        f"🎫 Credits: {data.get(_CREDITS)}\n"
        f"📄 TrxID: `{trx_id}`\n"
        f"🆔 Payment ID: {payment_id}"
    )
    from bot.utils.keyboards import admin_payment_keyboard
    for admin_id in settings.admin_id_list:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=msg,
        parse_mode="Markdown",
                reply_markup=admin_payment_keyboard(payment_id),
            )
        except Exception:
            logger.exception("Failed to notify admin %s", admin_id)


def build_credits_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💰 Buy Credits$"), show_packages),
        ],
        states={
            PAYMENT_SELECT_PACKAGE: [
                CallbackQueryHandler(package_selected, pattern=r"^pkg:"),
            ],
            PAYMENT_SELECT_METHOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, payment_method_selected),
            ],
            PAYMENT_SUBMIT_TRXID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_trxid),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$|^/cancel$"), cancel_payment),
            CallbackQueryHandler(cancel_payment, pattern="^pay:cancel$"),
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        allow_reentry=True,
        name="credits_purchase",
    )
