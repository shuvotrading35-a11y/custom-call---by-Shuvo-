"""
bot/handlers/user/redeem.py
Redeem code ConversationHandler
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from telegram import Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config.constants import CONVERSATION_TIMEOUT_SECONDS, REDEEM_ENTER_CODE
from bot.database.connection import get_session
from bot.database.models import RedeemCode, RedeemLog as RedeemUsage
from bot.services.credit_service import add_credits
from bot.utils.formatters import redeem_success_message, error_message
from bot.utils.keyboards import main_menu_keyboard, back_keyboard

logger = logging.getLogger(__name__)


async def ask_redeem_code(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "🎁 *Redeem Code*\n\nআপনার কোডটি টাইপ করুন:",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )
    return REDEEM_ENTER_CODE


async def process_redeem_code(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip().upper()
    uid = update.effective_user.id

    if text == "⬅️ Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    async with get_session() as db:
        # Fetch code
        result = await db.execute(
            select(RedeemCode).where(RedeemCode.code == text, RedeemCode.is_active == True)
        )
        code: RedeemCode | None = result.scalar_one_or_none()

        if not code:
            await update.message.reply_text(
                "❌ কোডটি সঠিক নয় অথবা নিষ্ক্রিয়।\n\nআবার চেষ্টা করুন:",
                reply_markup=back_keyboard(),
            )
            return REDEEM_ENTER_CODE

        # Expiry check
        if code.expires_at and code.expires_at < datetime.now(timezone.utc):
            await update.message.reply_text(
                "❌ এই কোডের মেয়াদ শেষ হয়ে গেছে।",
                reply_markup=main_menu_keyboard(),
            )
            return ConversationHandler.END

        # Max uses check
        if code.max_uses is not None and code.used_count >= code.max_uses:
            await update.message.reply_text(
                "❌ এই কোডের সর্বোচ্চ ব্যবহার সীমা পূর্ণ হয়েছে।",
                reply_markup=main_menu_keyboard(),
            )
            return ConversationHandler.END

        # Per-user limit check
        usage_result = await db.execute(
            select(func.count()).select_from(RedeemUsage).where(
                RedeemUsage.code_id == code.id,
                RedeemUsage.user_id == uid,
            )
        )
        user_usage_count = usage_result.scalar() or 0
        if user_usage_count >= code.max_per_user:
            await update.message.reply_text(
                "❌ আপনি এই কোড আগেই ব্যবহার করেছেন।",
                reply_markup=main_menu_keyboard(),
            )
            return ConversationHandler.END

        # Calculate credits
        if code.code_type == "gift":
            credits_to_add = code.credits
        elif code.code_type == "coupon":
            # Percentage bonus on current balance
            from bot.services.credit_service import get_balance
            balance = await get_balance(uid)
            credits_to_add = int(balance * code.bonus_percent / 100)
            if credits_to_add < 1:
                credits_to_add = code.credits  # fallback
        else:
            credits_to_add = code.credits

        # Record usage
        db.add(RedeemUsage(code_id=code.id, user_id=uid, credits=credits_to_add))
        code.used_count += 1
        await db.flush()

    # Add credits
    result = await add_credits(uid, credits_to_add, reason=f"redeem:{text}")
    if not result["success"]:
        await update.message.reply_text(
            error_message("ক্রেডিট যোগ করতে সমস্যা হয়েছে।"),
        parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        redeem_success_message(text, credits_to_add, result["balance_after"]),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


def build_redeem_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 Redeem$"), ask_redeem_code)],
        states={
            REDEEM_ENTER_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_redeem_code)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^/cancel$"), lambda u, c: ConversationHandler.END)
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        allow_reentry=True,
        name="redeem",
    )
