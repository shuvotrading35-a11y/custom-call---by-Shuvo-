"""
bot/database/connection.py
SQLite (aiosqlite) — simple, no external DB needed for Railway
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config.settings import settings
from bot.database.models import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _get_db_url() -> str:
    """Use SQLite if DATABASE_URL is default/empty, else use provided URL."""
    url = settings.DATABASE_URL
    if not url or "user:password@db" in url or url == "":
        logger.info("Using SQLite database (bot.db)")
        return "sqlite+aiosqlite:///bot.db"
    # Railway PostgreSQL URL fix: postgresql:// → postgresql+asyncpg://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        db_url = _get_db_url()
        connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
        _engine = create_async_engine(
            db_url,
            connect_args=connect_args,
            echo=settings.DEBUG,
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def close_db() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
