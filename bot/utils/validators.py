"""
bot/utils/validators.py
Bangladesh mobile number validation, normalization & operator detection
"""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ── Operator prefix map ───────────────────────────────────────────────────────
OPERATOR_MAP = {
    "017": "Grameenphone",
    "013": "Grameenphone",
    "018": "Robi",
    "016": "Airtel",
    "019": "Banglalink",
    "014": "Banglalink",
    "015": "Teletalk",
}

_STRIP_RE = re.compile(r"[\s\-\(\)\+]")


def normalize_bd_number(raw: str) -> Optional[str]:
    """
    Normalize any common BD mobile format to E.164 (+8801XXXXXXXXX).

    Accepted inputs:
        +8801XXXXXXXXX
         8801XXXXXXXXX
          01XXXXXXXXX
           1XXXXXXXXX   (rare — missing leading 0)

    Returns None if number is invalid / not a BD mobile.
    """
    if not raw:
        return None

    # Strip whitespace, dashes, parens, plus sign
    cleaned = _STRIP_RE.sub("", str(raw))

    # Remove country code variations
    if cleaned.startswith("880"):
        cleaned = cleaned[3:]           # → 01XXXXXXXXX or 1XXXXXXXXX

    # Ensure leading 0
    if cleaned.startswith("1") and len(cleaned) == 10:
        cleaned = "0" + cleaned         # → 01XXXXXXXXX

    # Must now be 11 digits starting with 01
    if not (len(cleaned) == 11 and cleaned.startswith("01") and cleaned.isdigit()):
        return None

    # Validate operator prefix (017, 013, 018 …)
    prefix = cleaned[:3]
    if prefix not in OPERATOR_MAP:
        return None

    return f"+880{cleaned[1:]}"         # → +8801XXXXXXXXX


def get_operator(number: str) -> Optional[str]:
    """Return operator name for a raw BD number, or None if unknown."""
    normalized = normalize_bd_number(number)
    if not normalized:
        return None
    # +880 1 7X... → local prefix = '0' + char at index 5
    prefix = "0" + normalized[4:7]      # e.g. "017"
    return OPERATOR_MAP.get(prefix)


def validate_bd_number(raw: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Full validation pipeline.

    Returns
    -------
    (is_valid, normalized_e164, operator_name)
    """
    normalized = normalize_bd_number(raw)
    if not normalized:
        return False, None, None
    operator = get_operator(raw)
    return True, normalized, operator


def is_valid_bd_number(raw: str) -> bool:
    """Quick boolean check."""
    return normalize_bd_number(raw) is not None


# ── Message validators ────────────────────────────────────────────────────────

def validate_message_length(text: str, max_chars: int = 500) -> Tuple[bool, int]:
    """Returns (is_valid, char_count)."""
    count = len(text)
    return count <= max_chars, count


def sanitize_message(text: str) -> str:
    """
    Basic sanitization before sending to Call API.
    Strips leading/trailing whitespace; collapses multiple spaces.
    """
    return re.sub(r"\s+", " ", text.strip())


# ── Credit validators ─────────────────────────────────────────────────────────

def validate_positive_int(value: str) -> Tuple[bool, Optional[int]]:
    """Parse and validate a positive integer from user input."""
    try:
        n = int(value.strip())
        if n > 0:
            return True, n
        return False, None
    except (ValueError, AttributeError):
        return False, None
