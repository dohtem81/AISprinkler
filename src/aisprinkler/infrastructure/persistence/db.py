"""Database engine and session helpers."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


_DEFAULT_DATABASE_URL = "postgresql+asyncpg://aisprinkler:aisprinkler@db:5432/aisprinkler"

_engine = None
_session_factory = None


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_database_url(), echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a single session per request."""
    async with get_session_factory()() as session:
        yield session
