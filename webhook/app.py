"""
webhook/app.py
FastAPI application — receives Telegram webhook updates
"""

import hashlib
import hmac
import logging

from fastapi import FastAPI, HTTPException, Request, Response
from telegram import Update
from telegram.ext import Application

from bot.config.settings import settings
from bot.config.logging_config import setup_logging, setup_sentry

logger = logging.getLogger(__name__)

# PTB Application instance (set by main.py)
_ptb_app: Application | None = None


def create_webhook_app(ptb_application: Application) -> FastAPI:
    global _ptb_app
    _ptb_app = ptb_application

    setup_logging(settings.LOG_LEVEL)
    setup_sentry(settings.SENTRY_DSN)

    app = FastAPI(title="Bangladesh Call Bot Webhook", docs_url=None, redoc_url=None)

    @app.on_event("startup")
    async def startup():
        await _ptb_app.initialize()
        logger.info("PTB application initialized")

    @app.on_event("shutdown")
    async def shutdown():
        await _ptb_app.shutdown()
        logger.info("PTB application shut down")

    @app.post("/webhook/{secret}")
    async def telegram_webhook(secret: str, request: Request) -> Response:
        # Verify webhook secret
        if secret != settings.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

        body = await request.json()
        update = Update.de_json(body, _ptb_app.bot)
        await _ptb_app.process_update(update)
        return Response(content="OK", status_code=200)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "bot": settings.BOT_USERNAME}

    return app
