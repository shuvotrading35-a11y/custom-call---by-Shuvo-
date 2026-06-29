"""
bot/middlewares/auth.py
PTB v21 compatible — TypeHandler based user registration + ban check
"""

import logging
from typing import Any, Callable

from sqlalchemy import select
from telegram import Update
from telegram.ext import CallbackContext

from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import User
from bot.utils.formatters import banned_message

logger = logging.getLogger(__name__)


async def user_middleware(update: Update, context: CallbackContext) -> None:
    if not update.effective_user:
        return

    tg_user = update.effective_user
    uid = tg_user.id

    try:
        async with get_session() as db:
            result = await db.execute(select(User).where(User.id == uid))
            user: User | None = result.scalar_one_or_none()

            full_name = f"{tg_user.first_name or ''} {tg_user.last_name or ''}".strip()

            if user is None:
                user = User(
                    id=uid,
                    username=tg_user.username,
                    full_name=full_name,
                )
                db.add(user)
                logger.info("New user: %s", uid)
            else:
                user.username  = tg_user.username
                user.full_name = full_name

            is_banned  = user.is_banned
            ban_reason = user.ban_reason

        if is_banned:
            if update.message:
                await update.message.reply_text(
                    banned_message(ban_reason), parse_mode="Markdown"
                )
            elif update.callback_query:
                await update.callback_query.answer("🚫 You are banned.", show_alert=True)
            return

    except Exception:
        logger.exception("Auth middleware error for user %s", uid)


def is_admin(user_id: int) -> bool:
    """Check if user_id is in ADMIN_IDS env variable."""
    admin_ids_str = settings.ADMIN_IDS
    if not admin_ids_str:
        return False
    try:
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        return user_id in admin_ids
    except Exception:
        return False


def admin_only(func: Callable) -> Callable:
    async def wrapper(update: Update, context: CallbackContext) -> Any:
        uid = update.effective_user.id if update.effective_user else None
        if not uid or not is_admin(uid):
            if update.message:
                await update.message.reply_text("⛔ Admins only.")
            elif update.callback_query:
                await update.callback_query.answer("⛔ Admins only.", show_alert=True)
            return
        return await func(update, context)
    return wrapper
