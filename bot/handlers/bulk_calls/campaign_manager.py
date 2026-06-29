"""
bot/handlers/bulk_calls/campaign_manager.py
Bulk campaign creation ConversationHandler
"""

import logging
from datetime import datetime

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
    BULK_CONFIRM,
    BULK_LANGUAGE,
    BULK_MESSAGE_TEXT,
    BULK_MESSAGE_TYPE,
    BULK_NAME,
    BULK_SCHEDULE,
    BULK_UPLOAD_RECIPIENTS,
    BULK_VOICE_TYPE,
    CONVERSATION_TIMEOUT_SECONDS,
)
from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import BulkCampaign, BulkRecipient
from bot.services.number_validator import bulk_validate_numbers
from bot.utils.formatters import error_message
from bot.utils.keyboards import (
    back_keyboard,
    campaign_actions_keyboard,
    language_keyboard,
    main_menu_keyboard,
    schedule_type_keyboard,
    voice_type_keyboard,
)
from bot.utils.file_parser import parse_recipient_file

logger = logging.getLogger(__name__)

# user_data keys
_NAME    = "camp_name"
_MSGTYPE = "camp_msg_type"
_MESSAGE = "camp_message"
_VOICE   = "camp_voice"
_LANG    = "camp_language"
_SCHED   = "camp_schedule"
_NUMS    = "camp_valid_numbers"


# ── Entry: Campaign name ──────────────────────────────────────────────────────
async def ask_campaign_name(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "📂 *Bulk Call Campaign*\n\n"
        "📝 Campaign-এর নাম দিন:",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )
    return BULK_NAME


async def receive_name(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    if text == "⬅️ Back":
        await update.message.reply_text("🏠", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    if len(text) < 2 or len(text) > 100:
        await update.message.reply_text("❌ ২–১০০ অক্ষরের নাম দিন:")
        return BULK_NAME

    context.user_data[_NAME] = text

    await update.message.reply_text(
        "📄 *Recipients আপলোড করুন*\n\n"
        "নিম্নলিখিত ফরম্যাটে নম্বর পাঠান:\n"
        "• 📄 CSV / TXT ফাইল\n"
        "• 📊 Excel (.xlsx)\n"
        "• ✍️ সরাসরি টাইপ করুন (কমা দিয়ে আলাদা)\n\n"
        "_শুধুমাত্র বাংলাদেশি নম্বর গ্রহণযোগ্য।_",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )
    return BULK_UPLOAD_RECIPIENTS


# ── Recipients upload ─────────────────────────────────────────────────────────
async def receive_recipients(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "⬅️ Back":
        return await ask_campaign_name(update, context)

    raw_numbers = []

    if update.message.document:
        file = await update.message.document.get_file()
        file_bytes = await file.download_as_bytearray()
        fname = update.message.document.file_name or "upload.csv"
        raw_numbers = await parse_recipient_file(file_bytes, fname)
    elif text:
        # Manual entry: comma/newline separated
        raw_numbers = [n.strip() for n in text.replace("\n", ",").split(",") if n.strip()]
    else:
        await update.message.reply_text("❌ ফাইল বা নম্বর পাঠান:")
        return BULK_UPLOAD_RECIPIENTS

    if not raw_numbers:
        await update.message.reply_text("❌ কোনো নম্বর পাওয়া যায়নি। আবার চেষ্টা করুন:")
        return BULK_UPLOAD_RECIPIENTS

    # Validate all numbers
    await update.message.reply_text("⏳ নম্বর যাচাই হচ্ছে...")
    validation = await bulk_validate_numbers(raw_numbers)
    valid   = validation["valid"]
    invalid = validation["invalid"]

    if not valid:
        await update.message.reply_text(
            f"❌ কোনো বৈধ বাংলাদেশি নম্বর পাওয়া যায়নি!\n\n"
            f"❌ Invalid: {len(invalid)}\n\n"
            "সঠিক নম্বর দিন:",
            reply_markup=back_keyboard(),
        )
        return BULK_UPLOAD_RECIPIENTS

    context.user_data[_NUMS] = valid

    summary = (
        f"✅ *Validation Complete*\n\n"
        f"✅ Valid     : {len(valid)}\n"
        f"❌ Invalid   : {len(invalid)}\n"
        f"🔄 Duplicates Removed: {validation['duplicates_removed']}\n"
        f"🚫 Blacklisted: {validation['blacklisted']}\n\n"
        "মেসেজ টাইপ বেছে নিন:"
    )

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=voice_type_keyboard(),
    )

    await update.message.reply_text(
        "📝 *Message Type*\n\n"
        "কোন পদ্ধতিতে কল যাবে?",
        
    )
    # Reuse voice_type_keyboard as message type selector is handled below
    return BULK_MESSAGE_TYPE


# ── Message type ──────────────────────────────────────────────────────────────
async def receive_message_type(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "⬅️ Back":
        await update.message.reply_text("নম্বর আবার আপলোড করুন:", reply_markup=back_keyboard())
        return BULK_UPLOAD_RECIPIENTS

    if text in ("📝 Text To Call", "TTS", "Text"):
        context.user_data[_MSGTYPE] = "tts"
        await update.message.reply_text(
            "📝 *Campaign Message*\n\nকল মেসেজ লিখুন (সর্বোচ্চ ৫০০ অক্ষর):",
        parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )
        return BULK_MESSAGE_TEXT
    elif text in ("🎤 Voice To Call", "Voice"):
        context.user_data[_MSGTYPE] = "voice"
        await update.message.reply_text(
            "🎤 *Voice Upload*\n\nঅডিও ফাইল পাঠান (OGG/MP3/WAV, সর্বোচ্চ ১০MB):",
        parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )
        return BULK_MESSAGE_TEXT
    else:
        await update.message.reply_text("📝 Text To Call অথবা 🎤 Voice To Call বেছে নিন:")
        return BULK_MESSAGE_TYPE


# ── Message / Voice content ───────────────────────────────────────────────────
async def receive_message_content(update: Update, context: CallbackContext) -> int:
    if update.message.text == "⬅️ Back":
        return BULK_MESSAGE_TYPE

    msg_type = context.user_data.get(_MSGTYPE, "tts")

    if msg_type == "tts":
        text = update.message.text.strip()
        if len(text) > 500:
            await update.message.reply_text(f"❌ মেসেজ বেশি বড় ({len(text)}/500)। ছোট করুন:")
            return BULK_MESSAGE_TEXT
        context.user_data[_MESSAGE] = text
    else:
        if update.message.audio or update.message.voice or update.message.document:
            file_obj = update.message.audio or update.message.voice or update.message.document
            context.user_data["camp_audio_file_id"] = file_obj.file_id
            context.user_data[_MESSAGE] = f"[Audio: {file_obj.file_id}]"
        else:
            await update.message.reply_text("❌ অডিও ফাইল পাঠান:")
            return BULK_MESSAGE_TEXT

    await update.message.reply_text(
        "🎙️ Voice Type বেছে নিন:",
        reply_markup=voice_type_keyboard(),
    )
    return BULK_VOICE_TYPE


# ── Voice type ────────────────────────────────────────────────────────────────
async def receive_voice_type(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "👩 Female":
        context.user_data[_VOICE] = "female"
    elif text == "👨 Male":
        context.user_data[_VOICE] = "male"
    elif text == "⬅️ Back":
        return BULK_MESSAGE_TEXT
    else:
        await update.message.reply_text("👩 Female অথবা 👨 Male:")
        return BULK_VOICE_TYPE

    await update.message.reply_text("🌐 Language:", reply_markup=language_keyboard())
    return BULK_LANGUAGE


# ── Language ──────────────────────────────────────────────────────────────────
async def receive_language(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "🇧🇩 বাংলা":
        context.user_data[_LANG] = "bn"
    elif text == "🇬🇧 English":
        context.user_data[_LANG] = "en"
    elif text == "⬅️ Back":
        return BULK_VOICE_TYPE
    else:
        await update.message.reply_text("🇧🇩 বাংলা অথবা 🇬🇧 English:")
        return BULK_LANGUAGE

    await update.message.reply_text(
        "🕐 Schedule Type:", reply_markup=schedule_type_keyboard()
    )
    return BULK_SCHEDULE


# ── Schedule ──────────────────────────────────────────────────────────────────
async def receive_schedule(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "⬅️ Back":
        return BULK_LANGUAGE

    sched_map = {
        "⚡ Immediate": "immediate",
        "🕐 Scheduled": "scheduled",
        "🔄 Recurring": "recurring",
    }
    if text not in sched_map:
        await update.message.reply_text("Schedule type বেছে নিন:")
        return BULK_SCHEDULE

    context.user_data[_SCHED] = sched_map[text]

    # Show summary
    valid_count = len(context.user_data.get(_NUMS, []))
    cost = valid_count * settings.BULK_CALL_CREDIT_COST

    summary = (
        "📋 *Campaign Summary*\n\n"
        f"📛 Name     : {context.user_data[_NAME]}\n"
        f"📞 Recipients: {valid_count:,}\n"
        f"📝 Type     : {context.user_data[_MSGTYPE].upper()}\n"
        f"🎙️ Voice    : {context.user_data[_VOICE].title()}\n"
        f"🌐 Language : {'বাংলা' if context.user_data[_LANG] == 'bn' else 'English'}\n"
        f"🕐 Schedule : {context.user_data[_SCHED].title()}\n"
        f"💳 Total Cost: {cost:,} Credits\n\n"
        "✅ শুরু করতে *Confirm* বাটন চাপুন।"
    )

    from bot.utils.keyboards import ReplyKeyboardMarkup
    confirm_kb = ReplyKeyboardMarkup(
        [["✅ Confirm Campaign", "❌ Cancel"]],
        resize_keyboard=True,
    )
    await update.message.reply_text(summary,  reply_markup=confirm_kb)
    return BULK_CONFIRM


# ── Confirm & Create ──────────────────────────────────────────────────────────
async def confirm_campaign(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    uid = update.effective_user.id

    if text == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text("❌ বাতিল।", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    if text != "✅ Confirm Campaign":
        return BULK_CONFIRM

    valid_numbers = context.user_data.get(_NUMS, [])
    cost = len(valid_numbers) * settings.BULK_CALL_CREDIT_COST

    # Check credits
    from bot.services.credit_service import has_sufficient_credits, deduct_credits, get_balance
    if not await has_sufficient_credits(uid, cost):
        balance = await get_balance(uid)
        await update.message.reply_text(
            f"❌ Credits কম!\n\nদরকার: {cost:,}\nআপনার: {balance:,}",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    # Deduct credits
    await deduct_credits(uid, cost, reason="bulk_campaign", actor_id=uid)

    await update.message.reply_text("⏳ Campaign তৈরি হচ্ছে...", reply_markup=main_menu_keyboard())

    async with get_session() as db:
        campaign = BulkCampaign(
            user_id      = uid,
            name         = context.user_data[_NAME],
            message_type = context.user_data[_MSGTYPE],
            message      = context.user_data.get(_MESSAGE),
            voice        = context.user_data[_VOICE],
            language     = context.user_data[_LANG],
            status       = "draft" if context.user_data[_SCHED] != "immediate" else "running",
            total_recipients = len(valid_numbers),
            schedule_type    = context.user_data[_SCHED],
            scheduled_at     = datetime.utcnow() if context.user_data[_SCHED] == "immediate" else None,
        )
        db.add(campaign)
        await db.flush()
        camp_id = campaign.id

        # Insert recipients
        for num_data in valid_numbers:
            db.add(BulkRecipient(
                campaign_id = camp_id,
                number      = num_data["number"],
                operator    = num_data["operator"],
                status      = "pending",
            ))

    # Dispatch Celery task
    try:
        from bot.tasks.bulk_tasks import run_bulk_campaign
        task = run_bulk_campaign.delay(camp_id)
        async with get_session() as db:
            from sqlalchemy import select as sel
            res = await db.execute(sel(BulkCampaign).where(BulkCampaign.id == camp_id))
            camp = res.scalar_one_or_none()
            if camp:
                camp.celery_task_id = task.id
    except Exception:
        logger.exception("Failed to dispatch Celery task for campaign %s", camp_id)

    await update.message.reply_text(
        f"✅ *Campaign #{camp_id} শুরু হয়েছে!*\n\n"
        f"📞 {len(valid_numbers):,} নম্বরে কল যাচ্ছে...\n\n"
        f"📊 Dashboard দেখতে: /campaign_{camp_id}",
        parse_mode="Markdown",
        reply_markup=campaign_actions_keyboard(camp_id, "running"),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_campaign(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ বাতিল।", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def build_bulk_campaign_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📂 Bulk Call$"), ask_campaign_name)],
        states={
            BULK_NAME:              [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            BULK_UPLOAD_RECIPIENTS: [
                MessageHandler(
                    (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
                    receive_recipients,
                )
            ],
            BULK_MESSAGE_TYPE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message_type)],
            BULK_MESSAGE_TEXT:  [
                MessageHandler(
                    (filters.TEXT | filters.AUDIO | filters.VOICE | filters.Document.ALL) & ~filters.COMMAND,
                    receive_message_content,
                )
            ],
            BULK_VOICE_TYPE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_voice_type)],
            BULK_LANGUAGE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_language)],
            BULK_SCHEDULE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_schedule)],
            BULK_CONFIRM:       [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_campaign)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$|^/cancel$"), cancel_campaign),
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        allow_reentry=True,
        name="bulk_campaign",
    )
