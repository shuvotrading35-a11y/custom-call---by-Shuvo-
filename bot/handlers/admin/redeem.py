"""
bot/handlers/admin/redeem.py
Admin Redeem Code Manager - Create, list, delete redeem codes
"""

import logging
import random
import string
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from telegram import Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.constants import CONVERSATION_TIMEOUT_SECONDS
from bot.database.connection import get_session
from bot.database.models import RedeemCode, RedeemLog
from bot.middlewares.auth import admin_only
from bot.utils.keyboards import admin_menu_keyboard

logger = logging.getLogger(__name__)

# States
(
    ADMIN_REDEEM_MENU,
    ADMIN_REDEEM_CREDITS,
    ADMIN_REDEEM_MAX_USES,
    ADMIN_REDEEM_EXPIRY,
    ADMIN_REDEEM_CUSTOM_CODE,
) = range(50, 55)


def generate_code(length: int = 10) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def redeem_admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ নতুন কোড তৈরি করুন", callback_data="radm:create")],
        [InlineKeyboardButton("📋 সব কোড দেখুন", callback_data="radm:list:0")],
        [InlineKeyboardButton("🗑️ কোড ডিলিট করুন", callback_data="radm:delete_menu")],
        [InlineKeyboardButton("🔙 Admin Menu", callback_data="radm:back")],
    ])


@admin_only
async def admin_redeem_entry(update: Update, context: CallbackContext) -> int:
    """Entry point when admin clicks 🎁 Redeems"""
    stats_text = await get_redeem_stats()
    await update.message.reply_text(
        f"🎁 <b>Redeem Code Manager</b>\n\n{stats_text}",
        parse_mode="HTML",
        reply_markup=redeem_admin_menu_keyboard(),
    )
    return ADMIN_REDEEM_MENU


async def get_redeem_stats() -> str:
    async with get_session() as db:
        total = await db.scalar(select(func.count()).select_from(RedeemCode))
        active = await db.scalar(
            select(func.count()).select_from(RedeemCode).where(RedeemCode.is_active == True)
        )
        total_used = await db.scalar(select(func.sum(RedeemCode.used_count)).select_from(RedeemCode)) or 0
    return (
        f"📊 মোট কোড: <b>{total}</b>\n"
        f"✅ সক্রিয় কোড: <b>{active}</b>\n"
        f"🔢 মোট ব্যবহার: <b>{total_used}</b>"
    )


async def handle_redeem_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "radm:back":
        await query.message.reply_text("🏠 Admin Menu", reply_markup=admin_menu_keyboard())
        await query.message.delete()
        return ConversationHandler.END

    elif data == "radm:create":
        context.user_data["radm"] = {}
        await query.message.edit_text(
            "➕ <b>নতুন Redeem কোড</b>\n\n"
            "💳 কতো ক্রেডিট দিতে চান? (শুধু সংখ্যা লিখুন)\n"
            "উদাহরণ: <code>50</code>",
            parse_mode="HTML",
        )
        return ADMIN_REDEEM_CREDITS

    elif data.startswith("radm:list"):
        page = int(data.split(":")[-1])
        await show_redeem_list(query, page)
        return ADMIN_REDEEM_MENU

    elif data.startswith("radm:toggle:"):
        code_id = int(data.split(":")[-1])
        await toggle_code(query, code_id)
        return ADMIN_REDEEM_MENU

    elif data.startswith("radm:del:"):
        code_id = int(data.split(":")[-1])
        await delete_code(query, code_id)
        return ADMIN_REDEEM_MENU

    elif data == "radm:delete_menu":
        await query.message.edit_text(
            "🗑️ <b>কোড ডিলিট</b>\n\n"
            "কোন ধরনের কোড ডিলিট করতে চান?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Expired কোড ডিলিট করুন", callback_data="radm:del_expired")],
                [InlineKeyboardButton("🗑️ সব নিষ্ক্রিয় কোড ডিলিট করুন", callback_data="radm:del_inactive")],
                [InlineKeyboardButton("🔙 ফিরে যান", callback_data="radm:list:0")],
            ])
        )
        return ADMIN_REDEEM_MENU

    elif data == "radm:del_expired":
        async with get_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(RedeemCode).where(
                    RedeemCode.expires_at != None,
                    RedeemCode.expires_at < now,
                )
            )
            codes = result.scalars().all()
            count = len(codes)
            for c in codes:
                await db.delete(c)
        await query.message.edit_text(
            f"✅ {count}টি expired কোড ডিলিট হয়েছে।",
            reply_markup=redeem_admin_menu_keyboard(),
        )
        return ADMIN_REDEEM_MENU

    elif data == "radm:del_inactive":
        async with get_session() as db:
            result = await db.execute(
                select(RedeemCode).where(RedeemCode.is_active == False)
            )
            codes = result.scalars().all()
            count = len(codes)
            for c in codes:
                await db.delete(c)
        await query.message.edit_text(
            f"✅ {count}টি নিষ্ক্রিয় কোড ডিলিট হয়েছে।",
            reply_markup=redeem_admin_menu_keyboard(),
        )
        return ADMIN_REDEEM_MENU

    return ADMIN_REDEEM_MENU


async def show_redeem_list(query, page: int = 0):
    per_page = 5
    offset = page * per_page

    async with get_session() as db:
        total = await db.scalar(select(func.count()).select_from(RedeemCode))
        result = await db.execute(
            select(RedeemCode).order_by(RedeemCode.created_at.desc()).offset(offset).limit(per_page)
        )
        codes = result.scalars().all()

    if not codes:
        await query.message.edit_text(
            "📋 কোনো redeem code নেই।",
            reply_markup=redeem_admin_menu_keyboard(),
        )
        return

    text = "📋 <b>Redeem Code List</b>\n\n"
    buttons = []

    for code in codes:
        status = "✅" if code.is_active else "❌"
        exp = code.expires_at.strftime("%d/%m/%y") if code.expires_at else "∞"
        text += (
            f"{status} <code>{code.code}</code>\n"
            f"   💳 {code.credits} ক্রেডিট | "
            f"🔢 {code.used_count}/{code.max_uses or '∞'} | "
            f"📅 {exp}\n\n"
        )
        toggle_label = "🔴 নিষ্ক্রিয় করুন" if code.is_active else "🟢 সক্রিয় করুন"
        buttons.append([
            InlineKeyboardButton(f"{code.code[:8]}.. {toggle_label}", callback_data=f"radm:toggle:{code.id}"),
            InlineKeyboardButton("🗑️", callback_data=f"radm:del:{code.id}"),
        ])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ আগে", callback_data=f"radm:list:{page-1}"))
    if offset + per_page < total:
        nav.append(InlineKeyboardButton("পরে ➡️", callback_data=f"radm:list:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="radm:back")])

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def toggle_code(query, code_id: int):
    async with get_session() as db:
        result = await db.execute(select(RedeemCode).where(RedeemCode.id == code_id))
        code = result.scalar_one_or_none()
        if code:
            code.is_active = not code.is_active
            status = "✅ সক্রিয়" if code.is_active else "❌ নিষ্ক্রিয়"
            await query.answer(f"{code.code} → {status}", show_alert=True)
        else:
            await query.answer("কোড পাওয়া যায়নি।", show_alert=True)

    await show_redeem_list(query, 0)


async def delete_code(query, code_id: int):
    async with get_session() as db:
        result = await db.execute(select(RedeemCode).where(RedeemCode.id == code_id))
        code = result.scalar_one_or_none()
        if code:
            code_text = code.code
            await db.delete(code)
            await query.answer(f"🗑️ {code_text} ডিলিট হয়েছে!", show_alert=True)
        else:
            await query.answer("কোড পাওয়া যায়নি।", show_alert=True)

    await show_redeem_list(query, 0)


# ── Step 1: Credits ──────────────────────────────────────────────────────────
async def get_credits(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন (যেমন: 50)")
        return ADMIN_REDEEM_CREDITS

    context.user_data["radm"]["credits"] = int(text)
    await update.message.reply_text(
        f"✅ ক্রেডিট: <b>{text}</b>\n\n"
        "🔢 সর্বোচ্চ কতোবার ব্যবহার করা যাবে?\n"
        "উদাহরণ: <code>100</code> অথবা <code>0</code> = সীমাহীন",
        parse_mode="HTML",
    )
    return ADMIN_REDEEM_MAX_USES


# ── Step 2: Max Uses ─────────────────────────────────────────────────────────
async def get_max_uses(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন। 0 = সীমাহীন")
        return ADMIN_REDEEM_MAX_USES

    val = int(text)
    context.user_data["radm"]["max_uses"] = None if val == 0 else val

    await update.message.reply_text(
        "📅 কোডের মেয়াদ কতোদিন?\n\n"
        "উদাহরণ:\n"
        "<code>7</code> = ৭ দিন\n"
        "<code>30</code> = ৩০ দিন\n"
        "<code>0</code> = মেয়াদ নেই",
        parse_mode="HTML",
    )
    return ADMIN_REDEEM_EXPIRY


# ── Step 3: Expiry ───────────────────────────────────────────────────────────
async def get_expiry(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন। 0 = মেয়াদ নেই")
        return ADMIN_REDEEM_EXPIRY

    days = int(text)
    context.user_data["radm"]["expires_at"] = (
        datetime.now(timezone.utc) + timedelta(days=days) if days > 0 else None
    )

    await update.message.reply_text(
        "🔤 কাস্টম কোড দিতে চান?\n\n"
        "কোড লিখুন (সর্বোচ্চ ৩২ অক্ষর) অথবা\n"
        "<code>AUTO</code> লিখুন স্বয়ংক্রিয় কোড পেতে",
        parse_mode="HTML",
    )
    return ADMIN_REDEEM_CUSTOM_CODE


# ── Step 4: Custom Code / Create ─────────────────────────────────────────────
async def create_code(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip().upper()
    data = context.user_data.get("radm", {})

    if text == "AUTO":
        code_str = generate_code()
    else:
        if len(text) < 4 or len(text) > 32:
            await update.message.reply_text("❌ কোড ৪-৩২ অক্ষরের হতে হবে।")
            return ADMIN_REDEEM_CUSTOM_CODE
        code_str = text

    credits = data.get("credits", 10)
    max_uses = data.get("max_uses", 1)
    expires_at = data.get("expires_at")
    uid = update.effective_user.id

    async with get_session() as db:
        # Duplicate check
        existing = await db.scalar(select(func.count()).select_from(RedeemCode).where(RedeemCode.code == code_str))
        if existing:
            await update.message.reply_text(
                f"❌ <code>{code_str}</code> কোডটি আগেই আছে। অন্য কোড দিন।",
                parse_mode="HTML",
            )
            return ADMIN_REDEEM_CUSTOM_CODE

        new_code = RedeemCode(
            code=code_str,
            code_type="gift",
            credits=credits,
            max_uses=max_uses,
            max_per_user=1,
            expires_at=expires_at,
            is_active=True,
            created_by=uid,
        )
        db.add(new_code)

    exp_text = expires_at.strftime("%d/%m/%Y") if expires_at else "সীমাহীন"
    uses_text = str(max_uses) if max_uses else "সীমাহীন"

    await update.message.reply_text(
        f"✅ <b>Redeem Code তৈরি হয়েছে!</b>\n\n"
        f"🔑 কোড: <code>{code_str}</code>\n"
        f"💳 ক্রেডিট: <b>{credits}</b>\n"
        f"🔢 ব্যবহার সীমা: <b>{uses_text}</b>\n"
        f"📅 মেয়াদ: <b>{exp_text}</b>\n\n"
        f"👆 কোড কপি করে ইউজারদের দিন।",
        parse_mode="HTML",
        reply_markup=redeem_admin_menu_keyboard(),
    )
    context.user_data.pop("radm", None)
    return ADMIN_REDEEM_MENU


def build_admin_redeem_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎁 Redeems$"), admin_redeem_entry)
        ],
        states={
            ADMIN_REDEEM_MENU: [
                CallbackQueryHandler(handle_redeem_callback, pattern="^radm:"),
            ],
            ADMIN_REDEEM_CREDITS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_credits),
            ],
            ADMIN_REDEEM_MAX_USES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_max_uses),
            ],
            ADMIN_REDEEM_EXPIRY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_expiry),
            ],
            ADMIN_REDEEM_CUSTOM_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_code),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^/cancel$"), lambda u, c: ConversationHandler.END),
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        allow_reentry=True,
        name="admin_redeem",
    )
