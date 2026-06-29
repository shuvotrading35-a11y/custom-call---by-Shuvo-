"""
bot/handlers/user/profile.py
User profile display handler
"""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import CallbackContext, MessageHandler, filters

from bot.database.connection import get_session
from bot.database.models import BulkCampaign, Call, Referral, User
from bot.utils.formatters import profile_message
from bot.utils.keyboards import profile_inline_keyboard

logger = logging.getLogger(__name__)


async def show_profile(update: Update, context: CallbackContext) -> None:
    uid = update.effective_user.id
    today = date.today()

    async with get_session() as db:
        user_result = await db.execute(select(User).where(User.id == uid))
        user: User | None = user_result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("Error: User not found.")
            return

        today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        calls_result = await db.execute(
            select(Call.status).where(Call.user_id == uid, Call.created_at >= today_start)
        )
        call_statuses = [row[0] for row in calls_result.fetchall()]

        today_calls   = len(call_statuses)
        success_calls = sum(1 for s in call_statuses if s == "completed")
        failed_calls  = sum(1 for s in call_statuses if s == "failed")

        camp_result = await db.execute(
            select(func.count()).select_from(BulkCampaign).where(BulkCampaign.user_id == uid)
        )
        campaigns = camp_result.scalar() or 0

        ref_result = await db.execute(
            select(Referral).where(Referral.referrer_id == uid)
        )
        referral_rows = ref_result.scalars().all()
        referral_count = len(referral_rows)
        referral_earned = sum(r.reward_credits for r in referral_rows if r.reward_paid)

    await update.message.reply_text(
        profile_message(
            user_id       = user.id,
            username      = user.username or "",
            full_name     = getattr(user, 'full_name', '') or '',
            joined        = user.joined_at,
            membership    = user.membership,
            credits       = user.credits,
            total_spent   = user.total_spent,
            today_calls   = today_calls,
            success_calls = success_calls,
            failed_calls  = failed_calls,
            campaigns     = campaigns,
            referrals     = referral_count,
            referral_earned = referral_earned,
        ),
        reply_markup=profile_inline_keyboard(),
    )


def register_profile_handler(app) -> None:
    app.add_handler(MessageHandler(filters.Regex("^👤 My Profile$"), show_profile))
