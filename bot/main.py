"""
bot/main.py
Entry point — PTB v21 compatible, no BaseMiddleware
"""

import asyncio
import logging
import sys

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, TypeHandler

from bot.config.logging_config import setup_logging, setup_sentry
from bot.config.settings import settings
from bot.database.connection import close_db, init_db
from bot.middlewares.auth import user_middleware

# Handler imports
from bot.handlers.user.start        import register_start_handlers
from bot.handlers.user.profile      import register_profile_handler
from bot.handlers.user.tts_call     import build_tts_call_handler
from bot.handlers.user.credits      import build_credits_handler
from bot.handlers.user.redeem       import build_redeem_handler
from bot.handlers.user.referral     import register_referral_handler
from bot.handlers.user.support      import build_support_handler
from bot.handlers.bulk_calls.campaign_manager import build_bulk_campaign_handler
from bot.handlers.admin.users       import register_admin_handlers

logger = logging.getLogger(__name__)


def build_application() -> Application:
    setup_logging(settings.LOG_LEVEL)
    setup_sentry(settings.SENTRY_DSN)

    app: Application = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .build()
    )

    # PTB v21 middleware via TypeHandler (runs before all other handlers)
    app.add_handler(TypeHandler(Update, user_middleware), group=-999)

    # ConversationHandlers
    app.add_handler(build_tts_call_handler())
    app.add_handler(build_credits_handler())
    app.add_handler(build_redeem_handler())
    app.add_handler(build_support_handler())
    app.add_handler(build_bulk_campaign_handler())

    # Simple handlers
    register_start_handlers(app)
    register_profile_handler(app)
    register_referral_handler(app)
    register_admin_handlers(app)

    logger.info("All handlers registered")
    return app


async def run_polling() -> None:
    await init_db()
    app = build_application()
    logger.info("Starting polling mode...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot running. Ctrl+C to stop.")
        await asyncio.Event().wait()


async def run_webhook() -> None:
    await init_db()
    app = build_application()
    webhook_url = f"{settings.WEBHOOK_URL}/webhook/{settings.WEBHOOK_SECRET}"
    await app.bot.set_webhook(url=webhook_url, secret_token=settings.WEBHOOK_SECRET)
    logger.info("Webhook: %s", webhook_url)

    from webhook.app import create_webhook_app
    import uvicorn
    fastapi_app = create_webhook_app(app)
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info")
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "polling"
    if mode == "webhook":
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())
