"""
bot/tasks/bulk_tasks.py
Celery tasks for bulk campaign execution
"""

import asyncio
import logging
from datetime import datetime

from bot.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="bulk_tasks.run_bulk_campaign", max_retries=3)
def run_bulk_campaign(self, campaign_id: int) -> dict:
    """
    Main Celery task: iterate over all pending recipients and make calls.
    Runs asynchronously via asyncio.run().
    """
    return asyncio.run(_async_run_campaign(campaign_id))


async def _async_run_campaign(campaign_id: int) -> dict:
    from sqlalchemy import select, update
    from bot.database.connection import get_session
    from bot.database.models import BulkCampaign, BulkRecipient, Call
    from bot.services.call_service import make_call
    from bot.config.settings import settings
    import asyncio

    logger.info("Starting bulk campaign %s", campaign_id)

    async with get_session() as db:
        result = await db.execute(select(BulkCampaign).where(BulkCampaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            logger.error("Campaign %s not found", campaign_id)
            return {"error": "Campaign not found"}

        campaign.status = "running"
        campaign.started_at = datetime.utcnow()
        await db.flush()

    completed = 0
    failed = 0

    # Process recipients in batches
    while True:
        async with get_session() as db:
            # Check if campaign is paused/cancelled
            result = await db.execute(select(BulkCampaign).where(BulkCampaign.id == campaign_id))
            camp = result.scalar_one_or_none()
            if not camp or camp.status in ("paused", "cancelled"):
                logger.info("Campaign %s stopped: %s", campaign_id, camp.status if camp else "deleted")
                break

            # Get next pending batch
            pending_result = await db.execute(
                select(BulkRecipient)
                .where(
                    BulkRecipient.campaign_id == campaign_id,
                    BulkRecipient.status == "pending",
                )
                .limit(camp.max_concurrent or 5)
            )
            batch = pending_result.scalars().all()

            if not batch:
                break  # All done

            message = camp.message or ""
            voice   = camp.voice or "female"
            user_id = camp.user_id

        # Process batch concurrently
        tasks = []
        for recipient in batch:
            tasks.append(_call_recipient(campaign_id, recipient.id, recipient.number, message, voice, user_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                failed += 1
            elif r.get("success"):
                completed += 1
            else:
                failed += 1

        # Update campaign progress
        async with get_session() as db:
            result = await db.execute(select(BulkCampaign).where(BulkCampaign.id == campaign_id))
            camp = result.scalar_one_or_none()
            if camp:
                camp.completed_count = completed
                camp.failed_count = failed

        # Interval between batches
        async with get_session() as db:
            result = await db.execute(select(BulkCampaign).where(BulkCampaign.id == campaign_id))
            camp = result.scalar_one_or_none()
            interval = camp.call_interval if camp else 2
        await asyncio.sleep(interval)

    # Mark campaign complete
    async with get_session() as db:
        result = await db.execute(select(BulkCampaign).where(BulkCampaign.id == campaign_id))
        camp = result.scalar_one_or_none()
        if camp and camp.status == "running":
            camp.status = "completed"
            camp.completed_at = datetime.utcnow()

    logger.info("Campaign %s done: completed=%s failed=%s", campaign_id, completed, failed)
    return {"campaign_id": campaign_id, "completed": completed, "failed": failed}


async def _call_recipient(
    campaign_id: int, recipient_id: int, number: str,
    message: str, voice: str, user_id: int
) -> dict:
    from sqlalchemy import select
    from bot.database.connection import get_session
    from bot.database.models import BulkRecipient, Call
    from bot.services.call_service import make_call
    from datetime import datetime

    # Mark as processing
    async with get_session() as db:
        res = await db.execute(select(BulkRecipient).where(BulkRecipient.id == recipient_id))
        recipient = res.scalar_one_or_none()
        if recipient:
            recipient.status = "processing"

    result = await make_call(number=number, message=message, voice=voice, user_id=user_id)

    # Update recipient status
    async with get_session() as db:
        res = await db.execute(select(BulkRecipient).where(BulkRecipient.id == recipient_id))
        recipient = res.scalar_one_or_none()
        if recipient:
            recipient.status = "completed" if result["success"] else "failed"
            recipient.processed_at = datetime.utcnow()
            if not result["success"]:
                recipient.error = result.get("error")

    return result
