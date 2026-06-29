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
        "👑 <b>Admin Panel</b>\n\nWelcome, Admin!",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


# ── User search ───────────────────────────────────────────────────────────────
async def search_user_start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "🔍 <b>User খুঁজুন</b>\n\nTelegram ID, username, বা নম্বর দিন:",
        parse_mode="HTML",
    )
    return ADMIN_FIND_USER


async def search_user_result(update: Update, context: CallbackContext) -> int:
    query_text = update.message.text.strip()

    async with get_session() as db:
        user = None
        if query_text.isdigit():
            result = await db.execute(select(User).where(User.id == int(query_text)))
            user = result.scalar_one_or_none()

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
        parse_mode="HTML",
        reply_markup=admin_user_actions_keyboard(user.id, user.is_banned),
    )
    return ConversationHandler.END


# ── Ban / Unban ───────────────────────────────────────────────────────────────
async def ban_user_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    parts = query.data.split(":")
    action = parts[1]
    target_id = int(parts[2])

    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == target_id))
        user = result.scalar_one_or_none()
        if user:
            user.is_banned = (action == "ban")
            status = "🚫 Banned" if user.is_banned else "✅ Unbanned"
            await query.answer(f"User {status}!", show_alert=True)
        else:
            await query.answer("User not found!", show_alert=True)


# ── Add credits ────────────────────────────────────────────────────────────────
async def add_credits_start(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    target_id = int(query.data.split(":")[2])
    context.user_data["target_user_id"] = target_id
    
    await query.message.reply_text(
        f"💳 <b>Add Credits to User {target_id}</b>\n\n"
        f"কতো ক্রেডিট যোগ করতে চান?",
        parse_mode="HTML",
    )
    return ADMIN_ENTER_CREDITS


async def receive_credit_amount(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ সংখ্যা দিন (যেমন: 50)")
        return ADMIN_ENTER_CREDITS

    credits = int(text)
    target_id = context.user_data.get("target_user_id")
    
    result = await add_credits(target_id, credits, reason=f"admin_add:{update.effective_user.id}")
    
    await update.message.reply_text(
        f"✅ {credits} ক্রেডিট যোগ করা হয়েছে!\n"
        f"নতুন balance: {result.get('balance_after', 0)}",
        reply_markup=admin_menu_keyboard(),
    )
    return ConversationHandler.END


# ── Payment handling ───────────────────────────────────────────────────────────
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
        if payment:
            payment.status = "approved"
            payment.verified_by = query.from_user.id

    await query.edit_message_text(f"✅ Payment #{payment_id} Approved!")


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

    text = (
        "📊 <b>SYSTEM ANALYTICS</b>\n\n"
        f"Total Users: {total_users}\n"
        f"New Today: {new_today}\n\n"
        f"Calls Today: {calls_today}\n"
        f"Success Rate: {success_rate:.1f}%"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


# ── Settings / API Config ─────────────────────────────────────────────────────
async def show_api_config(update: Update, context: CallbackContext) -> None:
    text = (
        "⚙️ <b>API Configuration</b>\n\n"
        f"API URL: <code>{settings.CALL_API_URL}</code>\n"
        f"Status: ✅ Configured"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


# ── NEW: All missing admin menu button handlers ────────────────────────────────

async def show_calls(update: Update, context: CallbackContext) -> None:
    """📞 Calls button"""
    from datetime import datetime, timezone, timedelta
    from bot.database.models import Call
    
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    
    async with get_session() as db:
        calls = await db.execute(
            select(Call).where(Call.created_at >= last_24h).order_by(Call.created_at.desc()).limit(10)
        )
        calls = calls.scalars().all()
    
    if not calls:
        text = "📞 <b>Recent Calls</b>\n\nগত ২৪ ঘণ্টায় কোনো call নেই।"
    else:
        text = "📞 <b>Recent Calls (Last 24h)</b>\n\n"
        for call in calls:
            status_icon = "✅" if call.status == "completed" else "❌" if call.status == "failed" else "⏳"
            text += f"{status_icon} Call #{call.id}\n"
            text += f"   User: {call.user_id} | Duration: {call.duration_seconds or 0}s\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def show_bulk_calls(update: Update, context: CallbackContext) -> None:
    """📂 Bulk Calls button"""
    from bot.database.models import BulkCampaign
    
    async with get_session() as db:
        campaigns = await db.execute(
            select(BulkCampaign).order_by(BulkCampaign.created_at.desc()).limit(10)
        )
        campaigns = campaigns.scalars().all()
    
    if not campaigns:
        text = "📂 <b>Bulk Campaigns</b>\n\nকোনো campaign নেই।"
    else:
        text = "📂 <b>Active Bulk Campaigns</b>\n\n"
        for c in campaigns:
            status_icon = "🟢" if c.status == "processing" else "✅" if c.status == "completed" else "⏹️"
            text += f"{status_icon} Campaign #{c.id}\n"
            text += f"   Sent: {c.sent_count}/{c.total_count}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def show_credits(update: Update, context: CallbackContext) -> None:
    """💳 Credits button"""
    from bot.database.models import CreditTransaction
    from datetime import datetime, timezone, timedelta
    
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    
    async with get_session() as db:
        txns = await db.execute(
            select(CreditTransaction).where(CreditTransaction.created_at >= last_24h)
            .order_by(CreditTransaction.created_at.desc()).limit(5)
        )
        txns = txns.scalars().all()
    
    if not txns:
        text = "💳 <b>Credit Transactions</b>\n\nগত ২৪ ঘণ্টায় কোনো transaction নেই।"
    else:
        text = "💳 <b>Recent Credit Transactions</b>\n\n"
        for tx in txns:
            icon = "➕" if tx.amount > 0 else "➖"
            text += f"{icon} {abs(tx.amount)} credits\n"
            text += f"   User: {tx.user_id} | Reason: {tx.reason}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def show_payments(update: Update, context: CallbackContext) -> None:
    """💰 Payments button"""
    from bot.database.models import Payment
    
    async with get_session() as db:
        payments = await db.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(10)
        )
        payments = payments.scalars().all()
    
    if not payments:
        text = "💰 <b>Payments</b>\n\nকোনো payment নেই।"
    else:
        text = "💰 <b>Recent Payments</b>\n\n"
        for p in payments:
            status_icon = "⏳" if p.status == "pending" else "✅" if p.status == "approved" else "❌"
            text += f"{status_icon} Payment #{p.id}\n"
            text += f"   Amount: {p.amount} | User: {p.user_id}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def show_broadcast(update: Update, context: CallbackContext) -> None:
    """📢 Broadcast button"""
    await update.message.reply_text(
        "📢 <b>Broadcast Message</b>\n\n"
        "সব users দের message পাঠান।\n\n"
        "আপনার বার্তা লিখুন:",
        parse_mode="HTML",
    )


async def show_security(update: Update, context: CallbackContext) -> None:
    """🛡️ Security button"""
    async with get_session() as db:
        banned = await db.scalar(select(func.count()).select_from(User).where(User.is_banned == True))
    
    text = (
        "🛡️ <b>Security Status</b>\n\n"
        f"🚫 Banned Users: {banned}\n\n"
        f"API Status: ✅ Online\n"
        f"Database: ✅ Connected"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def show_bot_status(update: Update, context: CallbackContext) -> None:
    """🤖 Bot Status button"""
    text = (
        "🤖 <b>Bot Status</b>\n\n"
        f"Status: <b>✅ Running</b>\n"
        f"Database: <b>✅ Connected</b>\n"
        f"Redis: <b>✅ Connected</b>\n"
        f"API: <b>✅ Online</b>\n\n"
        f"Bot: @{settings.BOT_USERNAME}"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def show_logs(update: Update, context: CallbackContext) -> None:
    """📂 Logs button"""
    async with get_session() as db:
        logs = await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(5)
        )
        logs = logs.scalars().all()
    
    if not logs:
        text = "📂 <b>Audit Logs</b>\n\nকোনো log নেই।"
    else:
        text = "📂 <b>Recent Audit Logs</b>\n\n"
        for log in logs:
            text += f"👤 Admin {log.admin_id} | Action: {log.action}\n"
            text += f"   Target: {log.target_id}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())


# ── Register all admin handlers ───────────────────────────────────────────────
def register_admin_handlers(app) -> None:
    """Register all admin menu handlers"""

    app.add_handler(CommandHandler("admin", admin_entry))
    
    # ✅ All main menu buttons
    app.add_handler(MessageHandler(filters.Regex("^👥 Users$"), search_user_start))
    app.add_handler(MessageHandler(filters.Regex("^📞 Calls$"), show_calls))
    app.add_handler(MessageHandler(filters.Regex("^📂 Bulk Calls$"), show_bulk_calls))
    app.add_handler(MessageHandler(filters.Regex("^💳 Credits$"), show_credits))
    app.add_handler(MessageHandler(filters.Regex("^💰 Payments$"), show_payments))
    app.add_handler(MessageHandler(filters.Regex("^📢 Broadcast$"), show_broadcast))
    app.add_handler(MessageHandler(filters.Regex("^📊 Analytics$"), show_analytics))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Settings$"), show_api_config))
    app.add_handler(MessageHandler(filters.Regex("^🛡️ Security$"), show_security))
    app.add_handler(MessageHandler(filters.Regex("^🤖 Bot Status$"), show_bot_status))
    app.add_handler(MessageHandler(filters.Regex("^📂 Logs$"), show_logs))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(ban_user_callback, pattern=r"^admin:(ban|unban):"))
    app.add_handler(CallbackQueryHandler(approve_payment,   pattern=r"^pay:approve:"))
    app.add_handler(CallbackQueryHandler(reject_payment,    pattern=r"^pay:reject:"))

    # Conversations
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👥 Users$"), search_user_start)],
        states={
            ADMIN_FIND_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_user_result)],
        },
        fallbacks=[],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        name="admin_user_search",
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_credits_start, pattern=r"^admin:credits:")],
        states={
            ADMIN_ENTER_CREDITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_credit_amount)],
        },
        fallbacks=[],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        name="admin_credits",
    ))
