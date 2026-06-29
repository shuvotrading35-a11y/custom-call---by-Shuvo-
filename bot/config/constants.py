"""
Application-wide constants.
"""

# ─── Bangladesh Operator Prefixes ────────────────────────────────────────────
BD_OPERATORS = {
    "017": "Grameenphone",
    "013": "Grameenphone",
    "018": "Robi",
    "016": "Airtel",
    "019": "Banglalink",
    "014": "Banglalink",
    "015": "Teletalk",
}

BD_VALID_PREFIXES = list(BD_OPERATORS.keys())

# ─── Call States ─────────────────────────────────────────────────────────────
class CallStatus:
    PENDING   = "pending"
    INITIATED = "initiated"
    SUCCESS   = "success"
    FAILED    = "failed"
    RETRY     = "retry"
    CANCELLED = "cancelled"

# ─── Campaign States ─────────────────────────────────────────────────────────
class CampaignStatus:
    DRAFT      = "draft"
    SCHEDULED  = "scheduled"
    RUNNING    = "running"
    PAUSED     = "paused"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"
    FAILED     = "failed"

# ─── Payment States ──────────────────────────────────────────────────────────
class PaymentStatus:
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    REFUNDED  = "refunded"

# ─── Payment Methods ─────────────────────────────────────────────────────────
class PaymentMethod:
    BKASH  = "bkash"
    NAGAD  = "nagad"
    ROCKET = "rocket"

# ─── Voice Options ───────────────────────────────────────────────────────────
class Voice:
    FEMALE = "female"
    MALE   = "male"

# ─── Languages ───────────────────────────────────────────────────────────────
class Language:
    BANGLA  = "bn"
    ENGLISH = "en"

# ─── Ticket Categories ───────────────────────────────────────────────────────
TICKET_CATEGORIES = [
    "💳 Payment Issue",
    "📞 Call Failed",
    "📂 Bulk Campaign Issue",
    "🎁 Redeem Problem",
    "🐛 Bug Report",
    "💡 Feature Request",
    "🔒 Security Concern",
]

# ─── Redeem Code Types ───────────────────────────────────────────────────────
class RedeemType:
    GIFT     = "gift"
    COUPON   = "coupon"
    REFERRAL = "referral"
    PROMO    = "promo"

# ─── Membership Tiers ────────────────────────────────────────────────────────
class Membership:
    FREE    = "Free"
    BASIC   = "Basic"
    PREMIUM = "Premium"
    VIP     = "VIP"

# ─── Pagination ──────────────────────────────────────────────────────────────
PAGE_SIZE = 10

# ─── Audio Formats ───────────────────────────────────────────────────────────
ALLOWED_AUDIO_FORMATS = ["ogg", "mp3", "wav", "m4a", "flac"]

# ─── Timeouts ────────────────────────────────────────────────────────────────
CONVERSATION_TIMEOUT_SECONDS = 300
FLOOD_LIMIT_MESSAGES = 5
FLOOD_LIMIT_WINDOW = 10

# ─── ConversationHandler States ──────────────────────────────────────────────

# TTS Call flow (0–6)
(
    CALL_TYPE_SELECT,
    CALL_ENTER_NUMBER,
    CALL_ENTER_MESSAGE,
    CALL_SELECT_VOICE,
    CALL_SELECT_LANGUAGE,
    CALL_PREVIEW,
    CALL_CONFIRM,
) = range(7)

# Voice Call flow (10–13)
(
    VOICE_UPLOAD_AUDIO,
    VOICE_ENTER_NUMBER,
    VOICE_PREVIEW,
    VOICE_CONFIRM,
) = range(10, 14)

# Bulk Campaign flow (20–29)
(
    BULK_NAME,
    BULK_DESCRIPTION,
    BULK_UPLOAD_RECIPIENTS,
    BULK_MESSAGE_TYPE,
    BULK_MESSAGE_TEXT,
    BULK_VOICE_UPLOAD,
    BULK_VOICE_TYPE,
    BULK_LANGUAGE,
    BULK_SCHEDULE,
    BULK_CONFIRM,
) = range(20, 30)

# Payment flow (40–43)
(
    PAYMENT_SELECT_PACKAGE,
    PAYMENT_SELECT_METHOD,
    PAYMENT_SUBMIT_TRXID,
    PAYMENT_UPLOAD_SCREENSHOT,
) = range(40, 44)

# Redeem (50)
REDEEM_ENTER_CODE = 50

# Support Ticket (60–62)
(
    SUPPORT_SELECT_CATEGORY,
    SUPPORT_DESCRIBE_ISSUE,
    SUPPORT_UPLOAD_SCREENSHOT,
) = range(60, 63)

# Admin flows (70–82)
(
    ADMIN_FIND_USER,
    ADMIN_ENTER_CREDITS,
    ADMIN_CONFIRM_CREDITS,
) = range(70, 73)

(
    ADMIN_BROADCAST_SELECT_TARGET,
    ADMIN_BROADCAST_ENTER_MESSAGE,
    ADMIN_BROADCAST_CONFIRM,
) = range(80, 83)
