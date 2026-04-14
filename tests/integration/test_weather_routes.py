"""Integration tests for the /api/v1/weather HTTP endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone
from typing import Any

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.api.routers import weather
from aisprinkler.infrastructure.persistence.db import get_db_session
from aisprinkler.infrastructure.persistence.models import (
    WeatherForecastHourModel,
    WeatherLocationModel,
)
from aisprinkler.infrastructure.scheduler import _di
from aisprinkler.infrastructure.weather.forecast_refresh import ForecastRefreshPort


def _override_factory(
    session: AsyncSession,
) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    return _override


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    test_app = FastAPI()
    test_app.include_router(weather.router, prefix="/api/v1/weather", tags=["weather"])
    test_app.dependency_overrides[get_db_session] = _override_factory(db_session)
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    test_app.dependency_overrides.clear()


async def test_refresh_weather_forecast_persists_rows(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    class _FakeRefreshProvider(ForecastRefreshPort):
        @property
        def provider_name(self) -> str:
            return "test_provider"

        async def fetch_forecast_hours(self, days: int = 7) -> list[dict[str, Any]]:
            assert days == 3
            return [
                {
                    "forecast_date": datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc).date(),
                    "forecast_hour": datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc),
                    "temperature_c": 25.0,
                    "feels_like_c": None,
                    "humidity_pct": 80.0,
                    "rain_mm": 1.2,
                    "snow_mm": 0.0,
                    "rain_probability_pct": 40.0,
                    "wind_speed_kmh": 8.0,
                    "wind_direction_deg": 180,
                    "weather_code": "61",
                    "weather_description": None,
                    "is_observed": False,
                    "provider": "test_provider",
                },
                {
                    "forecast_date": datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc).date(),
                    "forecast_hour": datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc),
                    "temperature_c": 24.5,
                    "feels_like_c": None,
                    "humidity_pct": 82.0,
                    "rain_mm": 0.8,
                    "snow_mm": 0.0,
                    "rain_probability_pct": 35.0,
                    "wind_speed_kmh": 6.0,
                    "wind_direction_deg": 190,
                    "weather_code": "51",
                    "weather_description": None,
                    "is_observed": False,
                    "provider": "test_provider",
                },
            ]

    monkeypatch.setattr(
        _di,
        "_build_refreshable_weather_provider",
        lambda: (
            _FakeRefreshProvider(),
            _di.WeatherProviderSettings(
                lat=30.676,
                lon=-87.914,
                zipcode="36527",
                city="Spanish Fort",
                state_code="AL",
            ),
        ),
    )

    response = await client.post(
        "/api/v1/weather/refresh",
        json={"days": 3, "device_id": str(uuid.uuid4())},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "refreshed"
    assert data["provider"] == "test_provider"
    assert data["days"] == 3
    assert data["rows_fetched"] == 2
    assert data["rows_persisted"] == 2

    locations = (await db_session.execute(select(WeatherLocationModel))).scalars().all()
    forecast_rows = (await db_session.execute(select(WeatherForecastHourModel))).scalars().all()

    assert len(locations) == 1
    assert len(forecast_rows) == 2
    assert locations[0].zipcode == data["zipcode"]
    assert {row.provider for row in forecast_rows} == {"test_provider"}


async def test_refresh_weather_forecast_rejects_unsupported_provider(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEATHER_PROVIDER", "synthetic")

    response = await client.post("/api/v1/weather/refresh")

    assert response.status_code == 400
    assert "does not support forecast refresh" in response.json()["detail"]
