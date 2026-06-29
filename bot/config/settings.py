"""
Application Settings — loaded from environment variables via pydantic-settings.
All secrets stay in .env — never hardcoded.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Telegram ────────────────────────────────────────────────────
    BOT_TOKEN: str
    BOT_USERNAME: str = "CallBot"
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    ADMIN_IDS: str = ""          # Comma-separated Telegram user IDs
    FORCE_JOIN_CHANNEL: str = "" # e.g. @your_channel

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: str) -> str:
        return v or ""

    @property
    def admin_id_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    # ─── Call API ────────────────────────────────────────────────────
    CALL_API_URL: str = "https://callapi.example.com/v1/send"
    CALL_API_KEY: str = ""           # Stored only in .env

    # ─── Database ────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/callbot"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ─── Redis / Celery ──────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ─── Payments ────────────────────────────────────────────────────
    BKASH_APP_KEY: str = ""
    BKASH_APP_SECRET: str = ""
    BKASH_USERNAME: str = ""
    BKASH_PASSWORD: str = ""
    BKASH_MERCHANT_NUMBER: str = ""

    NAGAD_MERCHANT_ID: str = ""
    NAGAD_MERCHANT_NUMBER: str = ""
    NAGAD_PG_KEY: str = ""

    ROCKET_MERCHANT_NUMBER: str = ""

    # ─── App ─────────────────────────────────────────────────────────
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "changeme"
    ENCRYPTION_KEY: str = ""

    MAX_CONCURRENT_CALLS: int = 20
    MAX_CALLS_PER_USER_PER_DAY: int = 100
    SINGLE_CALL_CREDIT_COST: int = 1
    BULK_CALL_CREDIT_COST: int = 1

    MAX_AUDIO_SIZE_MB: int = 10
    MAX_AUDIO_DURATION_SECONDS: int = 120

    REFERRAL_REWARD_CREDITS: int = 10

    # ─── Sentry ──────────────────────────────────────────────────────
    SENTRY_DSN: Optional[str] = None


# Singleton — import this everywhere
settings = Settings()
