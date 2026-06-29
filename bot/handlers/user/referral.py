"""
bot/handlers/user/referral.py
Referral system — show link, leaderboard, history
"""

import logging
import secrets
import string

from sqlalchemy import select, func
from telegram import Update
from telegram.ext import CallbackContext, MessageHandler, filters

from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import Referral, User
from bot.utils.formatters import referral_message
from bot.utils.keyboards import referral_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)


def _generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def show_referral(update: Update, context: CallbackContext) -> None:
    uid = update.effective_user.id

    async with get_session() as db:
        # Ensure user has a referral code
        result = await db.execute(select(User).where(User.id == uid))
        user: User | None = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ User not found.")
            return

        if not user.referral_code:
            user.referral_code = _generate_referral_code()
            await db.flush()

        referral_code = user.referral_code

        # Stats
        ref_result = await db.execute(
            select(Referral).where(Referral.referrer_id == uid)
        )
        referrals = ref_result.scalars().all()
        total_referrals = len(referrals)
        total_earned = sum(r.reward_credits for r in referrals if r.reward_paid)

    bot_username = settings.BOT_USERNAME.lstrip("@")  # strip @ if present in env
    referral_link = f"https://t.me/{bot_username}?start=ref_{referral_code}"

    await update.message.reply_text(
        referral_message(referral_link, total_referrals, total_earned),
        parse_mode="Markdown",
        reply_markup=referral_keyboard(referral_link),
    )


def register_referral_handler(app) -> None:
    app.add_handler(MessageHandler(filters.Regex("^👥 Refer$"), show_referral))
