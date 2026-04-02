"""Integration tests for the /api/v1/schedules HTTP endpoints.

These tests run against the real PostgreSQL instance in the docker-compose
network.  The session is provided via dependency_override so every test is
isolated and rolls back automatically.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import date, time

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.api.main import app
from aisprinkler.infrastructure.persistence.db import get_db_session


# ── Override get_db_session with the per-test db_session fixture ──────────────

def _override_factory(session: AsyncSession):
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    return _override


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Return an httpx AsyncClient backed by the test DB session."""
    app.dependency_overrides[get_db_session] = _override_factory(db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

_SCHEDULE_DATE = date(2026, 7, 15)
_START_TIME = time(5, 30)


def _body(device_id: uuid.UUID, **overrides) -> dict:
    return {
        "device_id": str(device_id),
        "schedule_date": _SCHEDULE_DATE.isoformat(),
        "start_time": _START_TIME.isoformat(),
        "duration_minutes": 20,
        **overrides,
    }


# ── GET /api/v1/schedules/ ────────────────────────────────────────────────────


async def test_list_schedules_empty(client: AsyncClient, device_in_db: uuid.UUID) -> None:
    response = await client.get(
        "/api/v1/schedules/",
        params={"device_id": str(device_in_db), "start_date": "2026-07-15", "days": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["original_baseline"] == []
    assert data["current_baseline"] == []


# ── POST /api/v1/schedules/ ───────────────────────────────────────────────────


async def test_create_current_schedule_returns_201(
    client: AsyncClient, device_in_db: uuid.UUID
) -> None:
    response = await client.post("/api/v1/schedules/", json=_body(device_in_db))
    assert response.status_code == 201
    data = response.json()
    assert data["baseline_kind"] == "current"
    assert data["duration_minutes"] == 20
    assert data["is_active"] is True
    assert data["superseded_at"] is None
    assert data["source"] == "manual"


async def test_create_current_schedule_appears_in_list(
    client: AsyncClient, device_in_db: uuid.UUID
) -> None:
    await client.post("/api/v1/schedules/", json=_body(device_in_db))

    response = await client.get(
        "/api/v1/schedules/",
        params={"device_id": str(device_in_db), "start_date": "2026-07-15", "days": 1},
    )
    assert response.status_code == 200
    current = response.json()["current_baseline"]
    assert len(current) == 1
    assert current[0]["duration_minutes"] == 20


async def test_create_supersedes_previous_slot(
    client: AsyncClient, device_in_db: uuid.UUID
) -> None:
    """A second POST for the same device/date/start_time supersedes the first."""
    first = await client.post("/api/v1/schedules/", json=_body(device_in_db, duration_minutes=20))
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = await client.post("/api/v1/schedules/", json=_body(device_in_db, duration_minutes=30))
    assert second.status_code == 201
    second_data = second.json()
    assert second_data["duration_minutes"] == 30
    assert second_data["superseded_at"] is None

    # Fetch history — include_history=True is the default for current in list
    list_resp = await client.get(
        "/api/v1/schedules/",
        params={"device_id": str(device_in_db), "start_date": "2026-07-15", "days": 1},
    )
    current = list_resp.json()["current_baseline"]
    ids = {row["id"] for row in current}
    assert first_id in ids  # superseded row still in history
    assert second_data["id"] in ids

    superseded = next(row for row in current if row["id"] == first_id)
    assert superseded["superseded_at"] is not None
    assert superseded["is_active"] is False


async def test_create_rejects_non_positive_duration(
    client: AsyncClient, device_in_db: uuid.UUID
) -> None:
    response = await client.post(
        "/api/v1/schedules/", json=_body(device_in_db, duration_minutes=0)
    )
    assert response.status_code == 422


# ── DELETE /api/v1/schedules/{schedule_id} ────────────────────────────────────


async def test_delete_deactivates_current_schedule(
    client: AsyncClient, device_in_db: uuid.UUID
) -> None:
    created = await client.post("/api/v1/schedules/", json=_body(device_in_db))
    schedule_id = created.json()["id"]

    delete_resp = await client.delete(f"/api/v1/schedules/{schedule_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deactivated"] is True

    list_resp = await client.get(
        "/api/v1/schedules/",
        params={"device_id": str(device_in_db), "start_date": "2026-07-15", "days": 1},
    )
    # With include_history=True the row is still returned but inactive
    current = list_resp.json()["current_baseline"]
    row = next(r for r in current if r["id"] == schedule_id)
    assert row["is_active"] is False


async def test_delete_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/schedules/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_returns_409_when_already_deactivated(
    client: AsyncClient, device_in_db: uuid.UUID
) -> None:
    created = await client.post("/api/v1/schedules/", json=_body(device_in_db))
    schedule_id = created.json()["id"]

    await client.delete(f"/api/v1/schedules/{schedule_id}")
    repeat = await client.delete(f"/api/v1/schedules/{schedule_id}")
    assert repeat.status_code == 409
