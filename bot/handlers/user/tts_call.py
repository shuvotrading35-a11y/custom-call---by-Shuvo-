"""
bot/handlers/user/tts_call.py
Text-to-Speech call flow (6-step ConversationHandler)
"""

import logging

from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config.constants import (
    CALL_CONFIRM,
    CALL_ENTER_MESSAGE,
    CALL_ENTER_NUMBER,
    CALL_PREVIEW,
    CALL_SELECT_LANGUAGE,
    CALL_SELECT_VOICE,
    CONVERSATION_TIMEOUT_SECONDS,
)
from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import Call
from bot.services.call_service import make_call
from bot.services.credit_service import deduct_credits, get_balance
from bot.services.number_validator import validate_and_check_number
from bot.utils.formatters import (
    call_failed_message,
    call_preview_message,
    call_success_message,
    error_message,
    insufficient_credits_message,
)
from bot.utils.keyboards import (
    back_keyboard,
    confirm_cancel_keyboard,
    language_keyboard,
    main_menu_keyboard,
    remove_keyboard,
    voice_type_keyboard,
)
from bot.utils.validators import sanitize_message, validate_message_length

logger = logging.getLogger(__name__)

# ── Data keys stored in context.user_data ────────────────────────────────────
_NUMBER   = "tts_number"
_OPERATOR = "tts_operator"
_MESSAGE  = "tts_message"
_VOICE    = "tts_voice"
_LANGUAGE = "tts_language"


# ── Step 1: Enter number ──────────────────────────────────────────────────────
async def ask_number(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "📞 *Step 1/5 — Bangladesh Number*\n\n"
        "কল করার নম্বরটি দিন:\n"
        "👉 `01XXXXXXXXX` ফরম্যাটে\n\n"
        "_শুধুমাত্র বাংলাদেশি নম্বর গ্রহণযোগ্য।_",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )
    return CALL_ENTER_NUMBER


async def receive_number(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()

    if text == "⬅️ Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    result = await validate_and_check_number(text)
    if not result["valid"]:
        await update.message.reply_text(
            f"❌ {result['error']}\n\nআবার সঠিক নম্বর দিন:",
            
        )
        return CALL_ENTER_NUMBER

    context.user_data[_NUMBER]   = result["normalized"]
    context.user_data[_OPERATOR] = result["operator"]

    await update.message.reply_text(
        f"✅ `{result['normalized']}` — *{result['operator']}*\n\n"
        "📝 *Step 2/5 — Your Message*\n\n"
        "কল মেসেজ লিখুন (সর্বোচ্চ ৫০০ অক্ষর):",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )
    return CALL_ENTER_MESSAGE


# ── Step 2: Enter message ─────────────────────────────────────────────────────
async def receive_message(update: Update, context: CallbackContext) -> int:
    text = update.message.text

    if text == "⬅️ Back":
        return await ask_number(update, context)

    is_valid, char_count = validate_message_length(text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ মেসেজ বেশি বড় ({char_count}/500 অক্ষর)। ছোট করুন:"
        )
        return CALL_ENTER_MESSAGE

    context.user_data[_MESSAGE] = sanitize_message(text)

    await update.message.reply_text(
        f"✅ মেসেজ সেট ({char_count}/500)\n\n"
        "🎙️ *Step 3/5 — Voice Type*\n\nকোন কণ্ঠস্বর চান?",
        parse_mode="Markdown",
        reply_markup=voice_type_keyboard(),
    )
    return CALL_SELECT_VOICE


# ── Step 3: Voice type ────────────────────────────────────────────────────────
async def receive_voice(update: Update, context: CallbackContext) -> int:
    text = update.message.text

    if text == "⬅️ Back":
        await update.message.reply_text("📝 মেসেজ আবার লিখুন:", reply_markup=back_keyboard())
        return CALL_ENTER_MESSAGE

    if text == "👩 Female":
        context.user_data[_VOICE] = "female"
    elif text == "👨 Male":
        context.user_data[_VOICE] = "male"
    else:
        await update.message.reply_text("👩 Female অথবা 👨 Male বেছে নিন:")
        return CALL_SELECT_VOICE

    await update.message.reply_text(
        "🌐 *Step 4/5 — Language*\n\nকোন ভাষায় কল হবে?",
        parse_mode="Markdown",
        reply_markup=language_keyboard(),
    )
    return CALL_SELECT_LANGUAGE


# ── Step 4: Language ──────────────────────────────────────────────────────────
async def receive_language(update: Update, context: CallbackContext) -> int:
    text = update.message.text

    if text == "⬅️ Back":
        await update.message.reply_text("🎙️ কণ্ঠস্বর বেছে নিন:", reply_markup=voice_type_keyboard())
        return CALL_SELECT_VOICE

    if text == "🇧🇩 বাংলা":
        context.user_data[_LANGUAGE] = "bn"
    elif text == "🇬🇧 English":
        context.user_data[_LANGUAGE] = "en"
    else:
        await update.message.reply_text("🇧🇩 বাংলা অথবা 🇬🇧 English বেছে নিন:")
        return CALL_SELECT_LANGUAGE

    # Show preview
    uid = update.effective_user.id
    cost = settings.SINGLE_CALL_CREDIT_COST

    preview = call_preview_message(
        number   = context.user_data[_NUMBER],
        operator = context.user_data[_OPERATOR],
        message  = context.user_data[_MESSAGE],
        voice    = context.user_data[_VOICE],
        language = context.user_data[_LANGUAGE],
        cost     = cost,
    )
    await update.message.reply_text(
        f"📋 *Step 5/5 — Preview*\n\n{preview}",
        parse_mode="Markdown",
        reply_markup=confirm_cancel_keyboard(),
    )
    return CALL_CONFIRM


# ── Step 5: Confirm ───────────────────────────────────────────────────────────
async def receive_confirm(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    uid  = update.effective_user.id

    if text == "❌ Cancel":
        await update.message.reply_text(
            "❌ Call বাতিল হয়েছে।",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    if text != "✅ Confirm & Call":
        await update.message.reply_text(
            "✅ Confirm & Call অথবা ❌ Cancel বেছে নিন।"
        )
        return CALL_CONFIRM

    cost = settings.SINGLE_CALL_CREDIT_COST
    number   = context.user_data[_NUMBER]
    message  = context.user_data[_MESSAGE]
    voice    = context.user_data[_VOICE]

    # Deduct credits
    deduct = await deduct_credits(uid, cost, reason="tts_call", actor_id=uid)
    if not deduct["success"]:
        balance = await get_balance(uid)
        await update.message.reply_text(
            insufficient_credits_message(cost, balance),
        parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text("⏳ Call পাঠানো হচ্ছে...", reply_markup=remove_keyboard())

    # Create call record in DB
    call_record_id = None
    try:
        async with get_session() as db:
            call_rec = Call(
                user_id    = uid,
                number     = number,
                operator   = context.user_data.get(_OPERATOR),
                call_type  = "tts",
                message    = message,
                voice      = voice,
                language   = context.user_data.get(_LANGUAGE),
                credits_used = cost,
                status     = "initiated",
            )
            db.add(call_rec)
            await db.flush()
            call_record_id = call_rec.id
    except Exception:
        logger.exception("Failed to create call record")

    # Make the call
    result = await make_call(
        number   = number,
        message  = message,
        voice    = voice,
        user_id  = uid,
        call_id  = call_record_id,
    )

    # Update call status in DB
    if call_record_id:
        try:
            async with get_session() as db:
                from sqlalchemy import select
                res = await db.execute(
                    __import__("sqlalchemy", fromlist=["select"]).select(Call).where(Call.id == call_record_id)
                )
                rec = res.scalar_one_or_none()
                if rec:
                    rec.status = "completed" if result["success"] else "failed"
                    rec.external_call_id = result.get("call_id")
                    rec.api_response = result
                    if not result["success"]:
                        rec.error_message = result.get("error")
        except Exception:
            logger.exception("Failed to update call record")

    if result["success"]:
        await update.message.reply_text(
            call_success_message(number, result.get("call_id")),
        parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
    else:
        # Refund credits on failure
        await deduct_credits.__module__
        from bot.services.credit_service import add_credits
        await add_credits(uid, cost, reason="call_failed_refund")
        await update.message.reply_text(
            call_failed_message(number, result.get("error", "Unknown")),
        parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_tts(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল।", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ── ConversationHandler factory ────────────────────────────────────────────────
def build_tts_call_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📝 Text To Call$"), ask_number),
        ],
        states={
            CALL_ENTER_NUMBER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
            CALL_ENTER_MESSAGE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message)],
            CALL_SELECT_VOICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_voice)],
            CALL_SELECT_LANGUAGE:[MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
            CALL_CONFIRM:        [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$|^/cancel$"), cancel_tts),
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        allow_reentry=True,
        name="tts_call",
    )
