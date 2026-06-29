"""
bot/tasks/payment_tasks.py
Celery tasks for payment verification and referral rewards
"""

import asyncio
import logging
from datetime import datetime, timedelta

from bot.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="bot.tasks.payment_tasks.process_pending_referrals")
def process_pending_referrals() -> dict:
    """Process referral rewards that have passed the 24-hour hold."""
    return asyncio.run(_async_process_referrals())


async def _async_process_referrals() -> dict:
    from sqlalchemy import select
    from bot.database.connection import get_session
    from bot.database.models import Referral
    from bot.services.credit_service import add_credits
    from bot.config.settings import settings

    hold_cutoff = datetime.utcnow() - timedelta(hours=24)
    processed = 0

    async with get_session() as db:
        result = await db.execute(
            select(Referral).where(
                Referral.reward_paid == False,
                Referral.created_at <= hold_cutoff,
            )
        )
        pending = result.scalars().all()

        for ref in pending:
            credit_result = await add_credits(
                ref.referrer_id,
                settings.REFERRAL_REWARD_CREDITS,
                reason=f"referral:{ref.referred_id}",
            )
            if credit_result["success"]:
                ref.reward_credits = settings.REFERRAL_REWARD_CREDITS
                ref.reward_paid = True
                ref.paid_at = datetime.utcnow()
                processed += 1

    logger.info("Processed %d referral rewards", processed)
    return {"processed": processed}
