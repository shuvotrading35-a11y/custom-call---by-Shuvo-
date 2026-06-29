"""
Logging configuration — rotating file + console + optional Sentry.
"""
import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    fmt = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, "bot.log"),
            maxBytes=10 * 1024 * 1024,   # 10 MB
            backupCount=5,
            encoding="utf-8",
        ),
    ]

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )

    # Quieten noisy libraries
    for lib in ("httpx", "httpcore", "telegram", "apscheduler", "celery"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def setup_sentry(dsn: str) -> None:
    """Initialize Sentry error tracking if DSN is provided."""
    if not dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
        )
        logging.getLogger(__name__).info("Sentry initialized")
    except ImportError:
        logging.getLogger(__name__).warning("sentry-sdk not installed, skipping")
    except Exception as e:
        logging.getLogger(__name__).warning("Sentry init failed: %s", e)
