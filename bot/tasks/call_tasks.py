"""
bot/tasks/call_tasks.py
Celery tasks for individual call retry logic
"""

import asyncio
import logging

from bot.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="call_tasks.retry_failed_call", max_retries=3, default_retry_delay=60)
def retry_failed_call(self, call_id: int) -> dict:
    """Retry a single failed call."""
    return asyncio.run(_async_retry_call(call_id))


async def _async_retry_call(call_id: int) -> dict:
    from sqlalchemy import select
    from bot.database.connection import get_session
    from bot.database.models import Call
    from bot.services.call_service import make_call

    async with get_session() as db:
        result = await db.execute(select(Call).where(Call.id == call_id))
        call = result.scalar_one_or_none()
        if not call:
            return {"error": "Call not found"}

        if call.status not in ("failed", "pending"):
            return {"error": f"Cannot retry call in status: {call.status}"}

        call.status = "initiated"

    result = await make_call(
        number=call.number,
        message=call.message or "",
        voice=call.voice or "female",
        user_id=call.user_id,
        call_id=call_id,
    )

    async with get_session() as db:
        res = await db.execute(select(Call).where(Call.id == call_id))
        c = res.scalar_one_or_none()
        if c:
            c.status = "completed" if result["success"] else "failed"
            c.external_call_id = result.get("call_id")
            c.api_response = result

    return result
