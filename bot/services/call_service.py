"""
bot/services/call_service.py
──────────────────────────────────────────────────────────────────
Single HTTP GET API voice call implementation.
No SDK. No VoIP. Just:  api_key + number + message + voice → call.
──────────────────────────────────────────────────────────────────
"""

import logging
import time
from typing import Optional

import aiohttp

from bot.config.settings import settings
from bot.database.connection import get_session
from bot.database.models import ApiLog, Call
from bot.utils.validators import normalize_bd_number

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

async def make_call(
    number: str,
    message: str,
    voice: str = "female",
    user_id: Optional[int] = None,
    call_id: Optional[int] = None,
) -> dict:
    """
    Dispatch a single TTS voice call via HTTP GET.

    Parameters
    ----------
    number  : BD mobile number (any format — normalized internally)
    message : Text message to read via TTS
    voice   : 'female' or 'male'
    user_id : Telegram user ID (for logging)
    call_id : DB call record ID (for logging)

    Returns
    -------
    {
        "success": bool,
        "call_id": str | None,      # external call ID from API
        "message": str | None,
        "error":   str | None,
    }
    """
    normalized = normalize_bd_number(number)
    if not normalized:
        return {"success": False, "error": "Invalid Bangladesh number"}

    params = {
        "api_key": settings.CALL_API_KEY,
        "number":  normalized,
        "message": message,
        "voice":   voice,
    }

    start_ms = int(time.monotonic() * 1000)
    result: dict = {}
    status_code: Optional[int] = None
    response_json: Optional[dict] = None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                settings.CALL_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                status_code = resp.status
                try:
                    response_json = await resp.json(content_type=None)
                except Exception:
                    raw = await resp.text()
                    response_json = {"raw": raw}

                if response_json.get("status") == "success":
                    result = {
                        "success":  True,
                        "call_id":  response_json.get("call_id"),
                        "message":  response_json.get("message", "Call initiated"),
                        "error":    None,
                    }
                    logger.info(
                        "Call dispatched | number=%s | ext_id=%s",
                        normalized, result.get("call_id"),
                    )
                else:
                    error_msg = response_json.get("message", "Unknown API error")
                    result = {"success": False, "call_id": None, "message": None, "error": error_msg}
                    logger.warning("Call API returned error | number=%s | err=%s", normalized, error_msg)

    except aiohttp.ClientTimeout:
        result = {"success": False, "call_id": None, "message": None, "error": "API timeout after 30s"}
        logger.error("Call API timeout | number=%s", normalized)

    except aiohttp.ClientConnectorError as exc:
        result = {"success": False, "call_id": None, "message": None, "error": f"Connection failed: {exc}"}
        logger.error("Call API connection error | number=%s | %s", normalized, exc)

    except Exception as exc:
        result = {"success": False, "call_id": None, "message": None, "error": f"Unexpected error: {exc}"}
        logger.exception("Unexpected error in make_call | number=%s", normalized)

    finally:
        latency = int(time.monotonic() * 1000) - start_ms
        await _log_api_call(
            call_id=call_id,
            user_id=user_id,
            number=normalized,
            message_preview=message[:100],
            voice=voice,
            status_code=status_code,
            response=response_json,
            latency_ms=latency,
            success=result.get("success", False),
        )

    return result


async def make_bulk_call(
    number: str,
    message: str,
    voice: str,
    campaign_id: int,
    user_id: Optional[int] = None,
    call_id: Optional[int] = None,
) -> dict:
    """
    Wrapper for bulk campaign calls — adds campaign tracking.
    """
    result = await make_call(
        number=number,
        message=message,
        voice=voice,
        user_id=user_id,
        call_id=call_id,
    )
    result["campaign_id"] = campaign_id
    result["number"] = number
    return result


async def test_api_connection(test_number: str = "01700000000") -> dict:
    """
    Admin function: test API reachability without a real call.
    Uses a dummy number — the API will reject it, but we verify connectivity.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                settings.CALL_API_URL,
                params={
                    "api_key": settings.CALL_API_KEY,
                    "number":  test_number,
                    "message": "API connection test",
                    "voice":   "female",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.json(content_type=None)
                return {
                    "reachable":    True,
                    "status_code":  resp.status,
                    "api_response": body,
                }
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _log_api_call(
    call_id: Optional[int],
    user_id: Optional[int],
    number: str,
    message_preview: str,
    voice: str,
    status_code: Optional[int],
    response: Optional[dict],
    latency_ms: int,
    success: bool,
) -> None:
    """Persist every API interaction to api_logs table."""
    try:
        async with get_session() as db:
            log = ApiLog(
                call_id=call_id,
                user_id=user_id,
                number=number,
                message_preview=message_preview,
                voice=voice,
                request_url=settings.CALL_API_URL,
                status_code=status_code,
                response=response,
                latency_ms=latency_ms,
                success=success,
            )
            db.add(log)
    except Exception:
        logger.exception("Failed to write api_log")
