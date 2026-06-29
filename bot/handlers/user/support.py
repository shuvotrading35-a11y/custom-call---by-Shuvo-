"""
bot/handlers/user/support.py
Support ticket creation and tracking ConversationHandler
"""

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config.constants import (
    CONVERSATION_TIMEOUT_SECONDS,
    SUPPORT_DESCRIBE_ISSUE,
    SUPPORT_SELECT_CATEGORY,
    SUPPORT_UPLOAD_SCREENSHOT,
)
from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import SupportTicket, TicketMessage as TicketReply
from bot.utils.keyboards import (
    main_menu_keyboard,
    ticket_category_keyboard,
    ticket_actions_keyboard,
    back_keyboard,
)

logger = logging.getLogger(__name__)

_CATEGORY = "ticket_category"


async def open_support(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "☎️ *Support*\n\nসমস্যার ক্যাটাগরি বেছে নিন:",
        parse_mode="Markdown",
        reply_markup=ticket_category_keyboard(),
    )
    return SUPPORT_SELECT_CATEGORY


async def category_selected(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data.split(":")[-1]

    category_map = {
        "payment": "💳 Payment Issue",
        "call":    "📞 Call Failed",
        "bulk":    "📂 Bulk Campaign Issue",
        "redeem":  "🎁 Redeem Problem",
        "bug":     "🐛 Bug Report",
        "feature": "💡 Feature Request",
        "security":"🔒 Security Concern",
    }
    context.user_data[_CATEGORY] = category_map.get(category, category)

    await query.edit_message_text(
        f"📋 Category: *{context.user_data[_CATEGORY]}*\n\n"
        "সমস্যাটি বিস্তারিত লিখুন:\n_(স্ক্রিনশট থাকলে পরের ধাপে দিন)_",
        
    )
    return SUPPORT_DESCRIBE_ISSUE


async def receive_description(update: Update, context: CallbackContext) -> int:
    description = update.message.text.strip()

    if len(description) < 10:
        await update.message.reply_text("❌ আরো বিস্তারিত লিখুন (কমপক্ষে ১০ অক্ষর):")
        return SUPPORT_DESCRIBE_ISSUE

    context.user_data["ticket_description"] = description

    await update.message.reply_text(
        "📸 *Optional: স্ক্রিনশট পাঠান*\n\n"
        "সমস্যার স্ক্রিনশট থাকলে পাঠান, না থাকলে *Skip* লিখুন:",
        
    )
    return SUPPORT_UPLOAD_SCREENSHOT


async def receive_screenshot(update: Update, context: CallbackContext) -> int:
    uid = update.effective_user.id
    screenshot_file_id = None

    if update.message.text and update.message.text.strip().lower() == "skip":
        pass  # No screenshot
    elif update.message.photo:
        screenshot_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        screenshot_file_id = update.message.document.file_id

    # Create ticket
    async with get_session() as db:
        ticket = SupportTicket(
            user_id     = uid,
            category    = context.user_data.get(_CATEGORY, "General"),
            subject     = context.user_data.get(_CATEGORY, "Support Request"),
            description = context.user_data.get("ticket_description", ""),
            screenshot_file_id = screenshot_file_id,
            status      = "open",
        )
        db.add(ticket)
        await db.flush()
        ticket_id = ticket.id

    # Notify admins
    await _notify_admins_ticket(context, uid, ticket_id, context.user_data)

    await update.message.reply_text(
        f"✅ *Ticket #{ticket_id} তৈরি হয়েছে!*\n\n"
        f"📋 Category: {context.user_data.get(_CATEGORY)}\n"
        "⏳ Admin শীঘ্রই দেখবেন। ধন্যবাদ! 🙏",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_support(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল।", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def _notify_admins_ticket(
    context: CallbackContext, user_id: int, ticket_id: int, data: dict
) -> None:
    msg = (
        "🎫 *নতুন Support Ticket!*\n\n"
        f"🆔 Ticket : #{ticket_id}\n"
        f"👤 User   : `{user_id}`\n"
        f"📋 Category: {data.get(_CATEGORY)}\n\n"
        f"📝 {data.get('ticket_description', '')[:200]}"
    )
    for admin_id in settings.admin_id_list:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=msg,
        parse_mode="Markdown",
                reply_markup=ticket_actions_keyboard(ticket_id, is_admin=True),
            )
        except Exception:
            logger.exception("Failed to notify admin %s of ticket", admin_id)


def build_support_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^☎️ Support$"), open_support)],
        states={
            SUPPORT_SELECT_CATEGORY: [
                CallbackQueryHandler(category_selected, pattern=r"^ticket:cat:")
            ],
            SUPPORT_DESCRIBE_ISSUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)
            ],
            SUPPORT_UPLOAD_SCREENSHOT: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
                    receive_screenshot,
                )
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^/cancel$"), cancel_support),
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        allow_reentry=True,
        name="support",
    )
