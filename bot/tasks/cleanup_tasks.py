"""
bot/tasks/cleanup_tasks.py
Scheduled cleanup tasks
"""

import asyncio
import logging
from datetime import datetime, timedelta

from bot.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="bot.tasks.cleanup_tasks.cleanup_old_logs")
def cleanup_old_logs() -> dict:
    return asyncio.run(_async_cleanup())


async def _async_cleanup() -> dict:
    from sqlalchemy import delete
    from bot.database.connection import get_session
    from bot.database.models import ApiLog, ErrorLog

    cutoff = datetime.utcnow() - timedelta(days=30)
    deleted = 0

    async with get_session() as db:
        result = await db.execute(delete(ApiLog).where(ApiLog.created_at < cutoff))
        deleted += result.rowcount
        result = await db.execute(delete(ErrorLog).where(ErrorLog.created_at < cutoff))
        deleted += result.rowcount

    logger.info("Cleanup: deleted %d old log records", deleted)
    return {"deleted": deleted}


# ── payment_tasks.py ──────────────────────────────────────────────────────────
