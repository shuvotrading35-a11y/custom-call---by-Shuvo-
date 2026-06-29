"""
bot/handlers/admin/users.py
Admin: user management — search, ban, credits, broadcast
"""

import logging

from sqlalchemy import select, func
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config.constants import (
    ADMIN_CONFIRM_CREDITS,
    ADMIN_ENTER_CREDITS,
    ADMIN_FIND_USER,
    ADMIN_BROADCAST_CONFIRM,
    ADMIN_BROADCAST_ENTER_MESSAGE,
    ADMIN_BROADCAST_SELECT_TARGET,
    CONVERSATION_TIMEOUT_SECONDS,
)
from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import AuditLog, User
from bot.middlewares.auth import admin_only, is_admin
from bot.services.credit_service import add_credits
from bot.utils.formatters import admin_user_detail_message
from bot.utils.keyboards import admin_menu_keyboard, admin_user_actions_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)


# ── /admin entry ──────────────────────────────────────────────────────────────
async def admin_entry(update: Update, context: CallbackContext) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admins only.")
        return
    await update.message.reply_text(
        "👑 *Admin Panel*\n\nWelcome, Admin!",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard(),
    )


# ── User search ───────────────────────────────────────────────────────────────
async def search_user_start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "🔍 User খুঁজুন:\n\nTelegram ID, username, বা নম্বর দিন:"
    )
    return ADMIN_FIND_USER


async def search_user_result(update: Update, context: CallbackContext) -> int:
    query_text = update.message.text.strip()
    uid = update.effective_user.id

    async with get_session() as db:
        # Try by numeric ID
        user = None
        if query_text.isdigit():
            result = await db.execute(select(User).where(User.id == int(query_text)))
            user = result.scalar_one_or_none()

        # Try by username
        if not user:
            clean = query_text.lstrip("@")
            result = await db.execute(select(User).where(User.username == clean))
            user = result.scalar_one_or_none()

    if not user:
        await update.message.reply_text("❌ User পাওয়া যায়নি। আবার চেষ্টা করুন:")
        return ADMIN_FIND_USER

    context.user_data["target_user_id"] = user.id
    await update.message.reply_text(
        admin_user_detail_message(user),
        parse_mode="Markdown",
        reply_markup=admin_user_actions_keyboard(user.id, user.is_banned),
    )
    return ConversationHandler.END


# ── Ban / Unban ───────────────────────────────────────────────────────────────
async def ban_user_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    action, user_id_str = query.data.split(":")[1], query.data.split(":")[2]
    target_id = int(user_id_str)

    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == target_id))
        user = result.scalar_one_or_none()
        if not user:
            await query.edit_message_text("❌ User not found.")
            return

        if action == "ban":
            user.is_banned = True
            user.ban_reason = "Banned by admin"
            msg = f"🚫 User `{target_id}` banned."
        else:
            user.is_banned = False
            user.ban_reason = None
            msg = f"✅ User `{target_id}` unbanned."

        db.add(AuditLog(
            actor_id=query.from_user.id,
            action=f"{action}_user",
            target_id=str(target_id),
            target_type="user",
        ))

    await query.edit_message_text(msg, )


# ── Add Credits ───────────────────────────────────────────────────────────────
async def add_credits_start(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[2])
    context.user_data["credit_target"] = target_id
    await query.message.reply_text(
        f"💳 User `{target_id}` কে কত Credits দেবেন? (সংখ্যা লিখুন)",
        
    )
    return ADMIN_ENTER_CREDITS


async def receive_credit_amount(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if not text.lstrip("-").isdigit():
        await update.message.reply_text("❌ সংখ্যা দিন:")
        return ADMIN_ENTER_CREDITS

    amount = int(text)
    target_id = context.user_data.get("credit_target")

    result = await add_credits(target_id, amount, reason="admin_grant", actor_id=update.effective_user.id)
    if result["success"]:
        await update.message.reply_text(
            f"✅ {amount} Credits যোগ হয়েছে!\n"
            f"User: `{target_id}`\n"
            f"New Balance: {result['balance_after']:,}",
        parse_mode="Markdown",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await update.message.reply_text(f"❌ {result['error']}")

    return ConversationHandler.END


# ── Payment approval callbacks ────────────────────────────────────────────────
async def approve_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    payment_id = int(query.data.split(":")[2])

    async with get_session() as db:
        from bot.database.models import Payment
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()

        if not payment or payment.status != "pending":
            await query.edit_message_text("❌ Payment not found or already processed.")
            return

        payment.status = "approved"
        payment.verified_by = query.from_user.id
        from datetime import datetime
        payment.verified_at = datetime.utcnow()
        await db.flush()
        user_id = payment.user_id
        credits = payment.credits

    # Add credits to user
    credit_result = await add_credits(user_id, credits, reason=f"payment:{payment_id}", actor_id=query.from_user.id)

    # Notify user
    try:
        from bot.utils.formatters import payment_approved_message
        await context.bot.send_message(
            chat_id=user_id,
            text=payment_approved_message(credits, credit_result.get("balance_after", 0)),
            
        )
    except Exception:
        logger.exception("Failed to notify user %s of payment approval", user_id)

    await query.edit_message_text(
        f"✅ Payment #{payment_id} Approved!\n"
        f"User: `{user_id}` | Credits: {credits}",
        
    )


async def reject_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    payment_id = int(query.data.split(":")[2])

    async with get_session() as db:
        from bot.database.models import Payment
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = "rejected"
            payment.verified_by = query.from_user.id

    await query.edit_message_text(f"❌ Payment #{payment_id} Rejected.")


# ── Analytics ─────────────────────────────────────────────────────────────────
async def show_analytics(update: Update, context: CallbackContext) -> None:
    from datetime import date, datetime, timezone
    from bot.database.models import Call, Payment

    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)

    async with get_session() as db:
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        new_today   = (await db.execute(
            select(func.count()).select_from(User).where(User.joined_at >= today_start)
        )).scalar() or 0

        calls_today = (await db.execute(
            select(func.count()).select_from(Call).where(Call.created_at >= today_start)
        )).scalar() or 0
        success_calls = (await db.execute(
            select(func.count()).select_from(Call).where(
                Call.created_at >= today_start, Call.status == "completed"
            )
        )).scalar() or 0
        success_rate = (success_calls / calls_today * 100) if calls_today else 0

        from bot.database.models import ApiLog
        avg_latency = (await db.execute(
            select(func.avg(ApiLog.latency_ms)).where(ApiLog.created_at >= today_start)
        )).scalar() or 0

    from bot.utils.formatters import admin_analytics_message
    await update.message.reply_text(
        admin_analytics_message({
            "total_users":    total_users,
            "active_today":   0,   # would need session tracking
            "new_today":      new_today,
            "calls_today":    calls_today,
            "success_rate":   success_rate,
            "bulk_campaigns": 0,
            "revenue_today":  0,
            "revenue_mtd":    0,
            "api_latency_ms": int(avg_latency),
        }),
        
    )


# ── API Config ────────────────────────────────────────────────────────────────
async def show_api_config(update: Update, context: CallbackContext) -> None:
    from bot.utils.formatters import api_config_message
    from bot.utils.keyboards import InlineKeyboardMarkup, InlineKeyboardButton

    await update.message.reply_text(
        api_config_message(settings.CALL_API_URL, settings.CALL_API_KEY),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🧪 Test API", callback_data="admin:api:test"),
        ]]),
    )


async def test_api_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer("Testing...")

    from bot.services.call_service import test_api_connection
    result = await test_api_connection()

    if result["reachable"]:
        await query.edit_message_text(
            f"✅ API Reachable!\n"
            f"Status: {result['status_code']}\n"
            f"Response: {str(result.get('api_response', {}))[:200]}",
        )
    else:
        await query.edit_message_text(f"❌ API Unreachable!\n\nError: {result.get('error')}")


# ── Register all admin handlers ───────────────────────────────────────────────
def register_admin_handlers(app) -> None:
    from bot.config.settings import settings as s

    app.add_handler(CommandHandler("admin", admin_entry))
    app.add_handler(MessageHandler(filters.Regex("^📊 Analytics$"), show_analytics))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Settings$"), show_api_config))

    # Callbacks
    app.add_handler(CallbackQueryHandler(ban_user_callback, pattern=r"^admin:(ban|unban):"))
    app.add_handler(CallbackQueryHandler(approve_payment,   pattern=r"^pay:approve:"))
    app.add_handler(CallbackQueryHandler(reject_payment,    pattern=r"^pay:reject:"))
    app.add_handler(CallbackQueryHandler(test_api_callback, pattern=r"^admin:api:test$"))

    # Add credits conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_credits_start, pattern=r"^admin:credits:")],
        states={
            ADMIN_ENTER_CREDITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_credit_amount)],
        },
        fallbacks=[],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        name="admin_credits",
    ))

    # User search conversation
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👥 Users$"), search_user_start)],
        states={
            ADMIN_FIND_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_user_result)],
        },
        fallbacks=[],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        name="admin_user_search",
    ))
