"""
bot/middlewares/rate_limiter.py
PTB v21 compatible — flood protection via Redis
"""

import logging
from telegram import Update
from telegram.ext import CallbackContext
from bot.config.constants import FLOOD_LIMIT_MESSAGES, FLOOD_LIMIT_WINDOW
from bot.config.settings import settings

logger = logging.getLogger(__name__)

_redis = None

def _get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def rate_limit_middleware(update: Update, context: CallbackContext) -> None:
    """Flood protection — called via TypeHandler."""
    if not update.effective_user:
        return
    uid = update.effective_user.id
    try:
        r = _get_redis()
        key = f"flood:{uid}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, FLOOD_LIMIT_WINDOW)
        if count > FLOOD_LIMIT_MESSAGES:
            if update.message:
                await update.message.reply_text(
                    f"⚠️ অনেক দ্রুত! {FLOOD_LIMIT_WINDOW} সেকেন্ড অপেক্ষা করুন।"
                )
            logger.warning("Rate limit: user %s", uid)
    except Exception:
        pass  # Redis unavailable — fail open
