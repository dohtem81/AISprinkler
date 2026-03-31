"""Integration test fixtures using docker-compose PostgreSQL service."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aisprinkler.infrastructure.persistence.models import Base, DeviceModel


def _db_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://aisprinkler:aisprinkler@db:5432/aisprinkler",
    )


@pytest_asyncio.fixture()
async def db_engine() -> AsyncGenerator[object, None]:
    engine = create_async_engine(_db_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine: object) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    async with session_factory() as session:
        yield session
        await session.rollback()  # isolate each test


@pytest_asyncio.fixture()
async def device_in_db(db_session: AsyncSession) -> uuid.UUID:
    """Insert a minimal device row to satisfy FK constraints on baseline_schedule."""
    device_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    model = DeviceModel(
        id=device_id,
        name="TestDevice",
        device_type="gpio_valve",
        timezone="America/Chicago",
        location_lat=32.361538,
        location_lon=-86.279118,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(model)
    await db_session.flush()
    return device_id
