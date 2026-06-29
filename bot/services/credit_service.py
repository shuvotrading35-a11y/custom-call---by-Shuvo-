"""
bot/services/credit_service.py
Credit ledger operations — atomic deduction / addition with DB locking
"""

import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.connection import get_session
from bot.database.models import User, AuditLog

logger = logging.getLogger(__name__)


async def get_balance(user_id: int) -> int:
    """Return current credit balance for a user."""
    async with get_session() as db:
        result = await db.execute(select(User.credits).where(User.id == user_id))
        return result.scalar_one_or_none() or 0


async def has_sufficient_credits(user_id: int, required: int) -> bool:
    balance = await get_balance(user_id)
    return balance >= required


async def deduct_credits(
    user_id: int,
    amount: int,
    reason: str = "call",
    actor_id: Optional[int] = None,
) -> dict:
    """
    Atomically deduct credits.

    Returns
    -------
    {"success": bool, "balance_before": int, "balance_after": int, "error": str|None}
    """
    async with get_session() as db:
        # Lock the row for update
        result = await db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"success": False, "error": "User not found"}

        balance_before = user.credits
        if balance_before < amount:
            return {
                "success": False,
                "balance_before": balance_before,
                "balance_after": balance_before,
                "error": f"Insufficient credits (have {balance_before}, need {amount})",
            }

        user.credits -= amount
        await db.flush()

        await _write_audit(db, actor_id or user_id, "deduct_credits", str(user_id), {
            "amount": amount, "reason": reason,
            "balance_before": balance_before, "balance_after": user.credits,
        })

        return {
            "success": True,
            "balance_before": balance_before,
            "balance_after": user.credits,
            "error": None,
        }


async def add_credits(
    user_id: int,
    amount: int,
    reason: str = "purchase",
    actor_id: Optional[int] = None,
) -> dict:
    """
    Atomically add credits to a user account.
    """
    async with get_session() as db:
        result = await db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"success": False, "error": "User not found"}

        balance_before = user.credits
        user.credits += amount
        await db.flush()

        await _write_audit(db, actor_id or user_id, "add_credits", str(user_id), {
            "amount": amount, "reason": reason,
            "balance_before": balance_before, "balance_after": user.credits,
        })

        logger.info("Credits added | user=%s | +%d | reason=%s", user_id, amount, reason)
        return {
            "success": True,
            "balance_before": balance_before,
            "balance_after": user.credits,
            "error": None,
        }


async def reset_credits(user_id: int, actor_id: int) -> dict:
    """Admin: reset user credits to 0."""
    async with get_session() as db:
        result = await db.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if not user:
            return {"success": False, "error": "User not found"}

        balance_before = user.credits
        user.credits = 0
        await _write_audit(db, actor_id, "reset_credits", str(user_id), {
            "balance_before": balance_before
        })

        return {"success": True, "balance_before": balance_before, "balance_after": 0}


# ── Internal ──────────────────────────────────────────────────────────────────
async def _write_audit(
    db: AsyncSession, actor_id: int, action: str, target: str, details: dict
) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_id=target, target_type="user", details=details))
