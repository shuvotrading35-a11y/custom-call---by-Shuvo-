"""
bot/services/number_validator.py
BD number validation service with blacklist cross-check
"""

import logging
from typing import Tuple, Optional

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import Blacklist
from bot.utils.validators import normalize_bd_number, get_operator, validate_bd_number

logger = logging.getLogger(__name__)


async def validate_and_check_number(raw: str) -> dict:
    """
    Full validation pipeline:
      1. Normalize to E.164
      2. Validate operator prefix
      3. Cross-check blacklist
      4. Return structured result

    Returns
    -------
    {
        "valid": bool,
        "normalized": str | None,
        "operator": str | None,
        "blacklisted": bool,
        "error": str | None,
    }
    """
    is_valid, normalized, operator = validate_bd_number(raw)

    if not is_valid:
        return {
            "valid": False,
            "normalized": None,
            "operator": None,
            "blacklisted": False,
            "error": "অবৈধ বাংলাদেশ মোবাইল নম্বর। সঠিক নম্বর দিন।",
        }

    # Blacklist check
    blacklisted = await _is_blacklisted(normalized)
    if blacklisted:
        logger.warning("Blacklisted number attempted: %s", normalized)
        return {
            "valid": False,
            "normalized": normalized,
            "operator": operator,
            "blacklisted": True,
            "error": "এই নম্বরটি ব্লকলিস্টে আছে।",
        }

    return {
        "valid": True,
        "normalized": normalized,
        "operator": operator,
        "blacklisted": False,
        "error": None,
    }


async def bulk_validate_numbers(raw_numbers: list[str]) -> dict:
    """
    Validate a list of numbers for bulk campaigns.

    Returns
    -------
    {
        "valid": list of {"number": normalized, "operator": ...},
        "invalid": list of {"raw": ..., "reason": ...},
        "duplicates_removed": int,
        "blacklisted": int,
    }
    """
    seen = set()
    valid = []
    invalid = []
    blacklisted_count = 0
    duplicates = 0

    for raw in raw_numbers:
        raw = str(raw).strip()
        if not raw:
            continue

        is_valid, normalized, operator = validate_bd_number(raw)

        if not is_valid:
            invalid.append({"raw": raw, "reason": "Invalid BD number format"})
            continue

        if normalized in seen:
            duplicates += 1
            continue
        seen.add(normalized)

        if await _is_blacklisted(normalized):
            blacklisted_count += 1
            invalid.append({"raw": raw, "reason": "Blacklisted"})
            continue

        valid.append({"number": normalized, "operator": operator})

    return {
        "valid": valid,
        "invalid": invalid,
        "duplicates_removed": duplicates,
        "blacklisted": blacklisted_count,
    }


async def _is_blacklisted(normalized_number: str) -> bool:
    """Check if a normalized number is on the blacklist."""
    try:
        async with get_session() as db:
            result = await db.execute(
                select(Blacklist).where(
                    Blacklist.type == "number",
                    Blacklist.value == normalized_number,
                )
            )
            return result.scalar_one_or_none() is not None
    except Exception:
        logger.exception("Blacklist check failed for %s", normalized_number)
        return False
