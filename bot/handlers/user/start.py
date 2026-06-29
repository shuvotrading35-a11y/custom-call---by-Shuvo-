"""
bot/handlers/user/start.py
/start command handler + main menu navigation
"""

import logging
from sqlalchemy import select, func

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from bot.database.connection import get_session
from bot.database.models import User
from bot.utils.formatters import welcome_message
from bot.utils.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: CallbackContext) -> None:
    """Handle /start — register user, show welcome, optionally process referral."""
    tg_user = update.effective_user
    if not tg_user:
        return

    uid = tg_user.id

    # Handle referral code from deep link: /start ref_XXXX
    referral_code = None
    if context.args:
        for arg in context.args:
            if arg.startswith("ref_"):
                referral_code = arg[4:]
                break

    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == uid))
        user: User | None = result.scalar_one_or_none()

        if user and referral_code and not user.referred_by:
            # Find referrer
            ref_result = await db.execute(
                select(User).where(User.referral_code == referral_code, User.id != uid)
            )
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                user.referred_by = referrer.id
                logger.info("User %s referred by %s", uid, referrer.id)

        credits = user.credits if user else 0

    name = tg_user.first_name or "বন্ধু"
    await update.message.reply_text(
        welcome_message(name, credits),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def main_menu_handler(update: Update, context: CallbackContext) -> None:
    """Show main menu on any unrecognized text while at top level."""
    await update.message.reply_text(
        "🏠 *Main Menu*\nনিচের বাটন চাপুন:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


def register_start_handlers(app) -> None:
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu",  main_menu_handler))
    app.add_handler(
        MessageHandler(filters.Regex("^🏠 Main Menu$"), main_menu_handler)
    )
    # Statistics button — show profile stats inline
    app.add_handler(
        MessageHandler(filters.Regex("^📊 Statistics$"), main_menu_handler)
    )
