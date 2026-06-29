"""
bot/utils/formatters.py
Message templates — Markdown formatted strings
"""

from datetime import datetime
from typing import Optional


def welcome_message(first_name: str, credits: int) -> str:
    return (
        f"🇧🇩 *আস্সালামু আলাইকুম, {first_name}!*\n\n"
        "✅ Bangladesh Custom Call Bot এ স্বাগতম!\n\n"
        "এই বটের মাধ্যমে আপনি:\n"
        "📝 Text-to-Speech কল পাঠাতে পারবেন\n"
        "🎤 ভয়েস রেকর্ডিং দিয়ে কল করতে পারবেন\n"
        "📂 Bulk Campaign চালাতে পারবেন\n\n"
        f"💳 আপনার ব্যালেন্স: *{credits} Credits*\n\n"
        "নিচের মেনু থেকে শুরু করুন"
    )


def profile_message(
    user_id: int,
    username: str,
    full_name: str,
    joined: datetime,
    membership: str,
    credits: int,
    total_spent: int,
    today_calls: int,
    success_calls: int,
    failed_calls: int,
    campaigns: int,
    referrals: int,
    referral_earned: int,
) -> str:
    uname = f"@{username}" if username else "N/A"
    joined_str = joined.strftime("%d %b %Y") if joined else "N/A"
    membership_emoji = {"free": "Free", "Free": "Free", "Premium": "Premium", "VIP": "VIP"}.get(membership, membership)

    return (
        "YOUR PROFILE\n\n"
        f"ID: {user_id}\n"
        f"Username: {uname}\n"
        f"Name: {full_name or 'N/A'}\n"
        f"Joined: {joined_str}\n"
        f"Membership: {membership_emoji}\n\n"
        f"Credits: {credits:,}\n"
        f"Total Spent: {total_spent:,} BDT\n\n"
        f"Today Calls: {today_calls}\n"
        f"Successful: {success_calls}\n"
        f"Failed: {failed_calls}\n"
        f"Bulk Campaigns: {campaigns}\n\n"
        f"Referrals: {referrals}\n"
        f"Referral Earned: {referral_earned} credits"
    )


def call_preview_message(number, operator, message, voice, language, cost) -> str:
    lang_display = "Bangla" if language == "bn" else "English"
    voice_display = "Female" if voice == "female" else "Male"
    return (
        "Call Preview\n\n"
        f"Number: {number}\n"
        f"Operator: {operator}\n"
        f"Voice: {voice_display}\n"
        f"Language: {lang_display}\n"
        f"Cost: {cost} Credit\n\n"
        f"Message:\n{message}\n\n"
        "Confirm করতে Confirm and Call চাপুন।"
    )


def call_success_message(number: str, ext_call_id: Optional[str]) -> str:
    call_ref = f"\nCall ID: {ext_call_id}" if ext_call_id else ""
    return (
        "Call Dispatched!\n\n"
        f"Number: {number}\n"
        f"Status: Initiated{call_ref}\n\n"
        "কিছুক্ষণের মধ্যে কল যাবে।"
    )


def call_failed_message(number: str, error: str) -> str:
    return (
        "Call Failed\n\n"
        f"Number: {number}\n"
        f"Error: {error}\n\n"
        "আবার চেষ্টা করুন বা Support এ যোগাযোগ করুন।"
    )


def insufficient_credits_message(required: int, balance: int) -> str:
    return (
        "Insufficient Credits\n\n"
        f"Required: {required} Credits\n"
        f"Your balance: {balance} Credits\n\n"
        "Buy Credits থেকে ক্রেডিট কিনুন।"
    )


def campaign_dashboard_message(campaign, stats: dict) -> str:
    total = stats.get("total", 0)
    completed = stats.get("completed", 0)
    failed = stats.get("failed", 0)
    success_rate = (completed / total * 100) if total else 0

    return (
        f"Campaign: {campaign.name}\n\n"
        f"Status: {campaign.status.upper()}\n\n"
        f"Total: {total:,}\n"
        f"Completed: {completed:,}\n"
        f"Failed: {failed:,}\n"
        f"Success Rate: {success_rate:.1f}%"
    )


def payment_instructions_message(method, merchant_number, amount, credits) -> str:
    method_name = method.title()
    return (
        f"{method_name} Payment\n\n"
        f"Amount: {amount} BDT\n"
        f"Credits: {credits}\n\n"
        f"Merchant Number: {merchant_number}\n\n"
        f"Step 1: {method_name} থেকে {amount} BDT পাঠান\n"
        "Step 2: Transaction ID কপি করুন\n"
        "Step 3: নিচে TrxID টাইপ করুন"
    )


def payment_submitted_message(trx_id, amount, credits) -> str:
    return (
        "Payment Submitted!\n\n"
        f"TrxID: {trx_id}\n"
        f"Amount: {amount} BDT\n"
        f"Credits: {credits}\n\n"
        "Admin verify করলে credits যোগ হবে।"
    )


def payment_approved_message(credits: int, balance: int) -> str:
    return (
        "Payment Approved!\n\n"
        f"{credits} Credits আপনার account এ যোগ হয়েছে।\n"
        f"New Balance: {balance:,} Credits"
    )


def redeem_success_message(code, credits, balance) -> str:
    return (
        "Redeem Successful!\n\n"
        f"Code: {code}\n"
        f"Credits: +{credits}\n"
        f"Balance: {balance:,} Credits"
    )


def referral_message(referral_link, total_referrals, total_earned) -> str:
    return (
        "Your Referral Info\n\n"
        f"Link: {referral_link}\n\n"
        f"Total Referrals: {total_referrals}\n"
        f"Total Earned: {total_earned} Credits\n\n"
        "নিচের লিংক শেয়ার করুন"
    )


def admin_analytics_message(stats: dict) -> str:
    return (
        "SYSTEM ANALYTICS\n\n"
        f"Total Users: {stats.get('total_users', 0):,}\n"
        f"New Today: {stats.get('new_today', 0):,}\n\n"
        f"Calls Today: {stats.get('calls_today', 0):,}\n"
        f"Success Rate: {stats.get('success_rate', 0):.1f}%\n\n"
        f"API Latency: {stats.get('api_latency_ms', 0)}ms"
    )


def admin_user_detail_message(user) -> str:
    uname = f"@{user.username}" if user.username else "N/A"
    status = "BANNED" if user.is_banned else "Active"
    full_name = getattr(user, 'full_name', None) or "N/A"
    return (
        "User Details\n\n"
        f"ID: {user.id}\n"
        f"Username: {uname}\n"
        f"Name: {full_name}\n"
        f"Credits: {user.credits:,}\n"
        f"Membership: {user.membership}\n"
        f"Joined: {user.joined_at.strftime('%d %b %Y') if user.joined_at else 'N/A'}\n"
        f"Status: {status}\n"
        + (f"Ban Reason: {user.ban_reason}\n" if user.is_banned and user.ban_reason else "")
    )


def api_config_message(api_url: str, api_key: str) -> str:
    masked_key = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
    return (
        "API Configuration\n\n"
        f"URL: {api_url}\n"
        f"Key: {masked_key}\n"
        "Method: GET\n\n"
        "Test করতে Test API বাটন চাপুন।"
    )


def error_message(text: str = "কিছু একটা ভুল হয়েছে। আবার চেষ্টা করুন।") -> str:
    return f"Error\n\n{text}"


def banned_message(reason: Optional[str] = None) -> str:
    base = "আপনি ব্যান হয়েছেন।\n\nআপনার অ্যাকাউন্ট suspended করা হয়েছে।"
    if reason:
        base += f"\n\nকারণ: {reason}"
    base += "\n\nঅভিযোগ থাকলে Support এ যোগাযোগ করুন।"
    return base
