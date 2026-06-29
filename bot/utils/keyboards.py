"""
bot/utils/keyboards.py
Centralized keyboard factory for all reply and inline keyboards
"""

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


# ═════════════════════════════════════════════════════════════════════════════
# REPLY KEYBOARDS
# ═════════════════════════════════════════════════════════════════════════════

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu for regular users."""
    return ReplyKeyboardMarkup(
        [
            ["📝 Text To Call",  "📂 Bulk Call"],
            ["👤 My Profile",    "👥 Refer"],
            ["📊 Statistics",    "💰 Buy Credits"],
            ["🎁 Redeem",        "☎️ Support"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="⚡ BY SHUVO......",
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu for admins."""
    return ReplyKeyboardMarkup(
        [
            ["👥 Users",      "📞 Calls",     "📂 Bulk Calls"],
            ["💳 Credits",    "💰 Payments",  "🎁 Redeems"],
            ["📢 Broadcast",  "📊 Analytics", "📂 Logs"],
            ["⚙️ Settings",   "🛡️ Security",  "🤖 Bot Status"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def call_type_keyboard() -> ReplyKeyboardMarkup:
    """Call type selection: TTS or Voice."""
    return ReplyKeyboardMarkup(
        [
            ["📝 Text To Call"],
            ["🎤 Voice To Call"],
            ["⬅️ Back"],
        ],
        resize_keyboard=True,
    )


def voice_type_keyboard() -> ReplyKeyboardMarkup:
    """Voice type: Female / Male."""
    return ReplyKeyboardMarkup(
        [["👩 Female", "👨 Male"], ["⬅️ Back"]],
        resize_keyboard=True,
    )


def language_keyboard() -> ReplyKeyboardMarkup:
    """Language selection."""
    return ReplyKeyboardMarkup(
        [["🇧🇩 বাংলা", "🇬🇧 English"], ["⬅️ Back"]],
        resize_keyboard=True,
    )


def confirm_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Generic confirm/cancel keyboard."""
    return ReplyKeyboardMarkup(
        [["✅ Confirm & Call", "❌ Cancel"]],
        resize_keyboard=True,
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    """Single back button."""
    return ReplyKeyboardMarkup([["⬅️ Back"]], resize_keyboard=True)


def payment_method_keyboard() -> ReplyKeyboardMarkup:
    """Payment gateway selection."""
    return ReplyKeyboardMarkup(
        [
            ["💚 bKash",  "🟠 Nagad"],
            ["🟣 Rocket", "⬅️ Back"],
        ],
        resize_keyboard=True,
    )


def schedule_type_keyboard() -> ReplyKeyboardMarkup:
    """Bulk campaign schedule type."""
    return ReplyKeyboardMarkup(
        [
            ["⚡ Immediate"],
            ["🕐 Scheduled"],
            ["🔄 Recurring"],
            ["⬅️ Back"],
        ],
        resize_keyboard=True,
    )


def recurrence_keyboard() -> ReplyKeyboardMarkup:
    """Recurring schedule options."""
    return ReplyKeyboardMarkup(
        [["Once", "Daily", "Weekly"], ["⬅️ Back"]],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ═════════════════════════════════════════════════════════════════════════════
# INLINE KEYBOARDS
# ═════════════════════════════════════════════════════════════════════════════

# ── Profile ───────────────────────────────────────────────────────────────────
def profile_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 History",  callback_data="profile:history"),
            InlineKeyboardButton("🎁 Refer",    callback_data="profile:refer"),
            InlineKeyboardButton("⚙️ Settings", callback_data="profile:settings"),
        ]
    ])


# ── Credits / Packages ────────────────────────────────────────────────────────
def credit_packages_keyboard(packages: list) -> InlineKeyboardMarkup:
    """Build inline keyboard from DB credit packages."""
    rows = []
    for pkg in packages:
        label = f"💳 {pkg.credits} Credits — ৳{pkg.price_bdt}"
        if pkg.bonus:
            label += f" (+{pkg.bonus} bonus)"
        rows.append([InlineKeyboardButton(label, callback_data=f"pkg:{pkg.id}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="pkg:cancel")])
    return InlineKeyboardMarkup(rows)


# ── Call history pagination ───────────────────────────────────────────────────
def pagination_keyboard(page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}:page:{page-1}"))
    buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}:page:{page+1}"))
    return InlineKeyboardMarkup([buttons])


# ── Campaign management ───────────────────────────────────────────────────────
def campaign_actions_keyboard(campaign_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    cid = campaign_id

    if status == "running":
        rows.append([
            InlineKeyboardButton("⏸ Pause",   callback_data=f"camp:pause:{cid}"),
            InlineKeyboardButton("⏹ Cancel",  callback_data=f"camp:cancel:{cid}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"camp:refresh:{cid}"),
        ])
    elif status == "paused":
        rows.append([
            InlineKeyboardButton("▶️ Resume",  callback_data=f"camp:resume:{cid}"),
            InlineKeyboardButton("⏹ Cancel",  callback_data=f"camp:cancel:{cid}"),
        ])
    elif status in ("draft", "scheduled"):
        rows.append([
            InlineKeyboardButton("▶️ Start",   callback_data=f"camp:start:{cid}"),
            InlineKeyboardButton("✏️ Edit",    callback_data=f"camp:edit:{cid}"),
            InlineKeyboardButton("🗑️ Delete",  callback_data=f"camp:delete:{cid}"),
        ])
    else:  # completed / failed / cancelled
        rows.append([
            InlineKeyboardButton("📋 Duplicate", callback_data=f"camp:dup:{cid}"),
            InlineKeyboardButton("📥 Report",    callback_data=f"camp:report:{cid}"),
            InlineKeyboardButton("🗑️ Delete",   callback_data=f"camp:delete:{cid}"),
        ])

    rows.append([InlineKeyboardButton("📊 Dashboard", callback_data=f"camp:dash:{cid}")])
    return InlineKeyboardMarkup(rows)


# ── Support tickets ───────────────────────────────────────────────────────────
def ticket_category_keyboard() -> InlineKeyboardMarkup:
    categories = [
        ("💳 Payment Issue",      "ticket:cat:payment"),
        ("📞 Call Failed",        "ticket:cat:call"),
        ("📂 Bulk Campaign",      "ticket:cat:bulk"),
        ("🎁 Redeem Problem",     "ticket:cat:redeem"),
        ("🐛 Bug Report",         "ticket:cat:bug"),
        ("💡 Feature Request",    "ticket:cat:feature"),
        ("🔒 Security Concern",   "ticket:cat:security"),
    ]
    rows = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in categories]
    return InlineKeyboardMarkup(rows)


def ticket_actions_keyboard(ticket_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("💬 Reply", callback_data=f"ticket:reply:{ticket_id}")]]
    if is_admin:
        rows.append([
            InlineKeyboardButton("✅ Resolve",    callback_data=f"ticket:resolve:{ticket_id}"),
            InlineKeyboardButton("🔒 Close",      callback_data=f"ticket:close:{ticket_id}"),
        ])
    return InlineKeyboardMarkup(rows)


# ── Admin: user actions ───────────────────────────────────────────────────────
def admin_user_actions_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton("✅ Unban",    callback_data=f"admin:unban:{user_id}")
        if is_banned
        else InlineKeyboardButton("🚫 Ban",  callback_data=f"admin:ban:{user_id}")
    )
    return InlineKeyboardMarkup([
        [ban_btn, InlineKeyboardButton("💳 Add Credits", callback_data=f"admin:credits:{user_id}")],
        [
            InlineKeyboardButton("📊 History",  callback_data=f"admin:history:{user_id}"),
            InlineKeyboardButton("📨 Message",  callback_data=f"admin:msg:{user_id}"),
        ],
        [
            InlineKeyboardButton("🚫 Blacklist", callback_data=f"admin:blacklist:{user_id}"),
            InlineKeyboardButton("📤 Export",    callback_data=f"admin:export:{user_id}"),
        ],
    ])


# ── Admin: payment approval ───────────────────────────────────────────────────
def admin_payment_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"pay:approve:{payment_id}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"pay:reject:{payment_id}"),
    ]])


# ── Referral ──────────────────────────────────────────────────────────────────
def referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔗 Share Referral Link", url=f"https://t.me/share/url?url={referral_link}")
    ]])


# ── Cancel only ──────────────────────────────────────────────────────────────
def cancel_inline_keyboard(prefix: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data=prefix)
    ]])
