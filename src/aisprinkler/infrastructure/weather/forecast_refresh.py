"""Provider-neutral forecast refresh contract and row normalization helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from aisprinkler.domain.value_objects.weather_context import WeatherContext


class ForecastRefreshPort(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable provider identifier persisted with normalized forecast rows."""

    @abstractmethod
    async def fetch_forecast_hours(self, days: int = 7) -> list[dict[str, Any]]:
        """Fetch normalized hourly forecast rows for persistence."""


def build_weather_context_from_rows(
    rows: list[dict[str, Any]],
    as_of: datetime,
    *,
    provider_name: str,
) -> WeatherContext:
    if not rows:
        return WeatherContext(
            rain_last_24h_mm=0.0,
            rain_forecast_next_24h_mm=0.0,
            rain_probability_pct=0.0,
            provider=provider_name,
            is_fallback_provider=False,
        )

    now = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=timezone.utc)
    past_cutoff = now - timedelta(hours=24)
    future_cutoff = now + timedelta(hours=24)

    last_24h_rain = sum(
        row["rain_mm"] or 0.0
        for row in rows
        if past_cutoff <= row["forecast_hour"] <= now
    )
    next_rows = [row for row in rows if now < row["forecast_hour"] <= future_cutoff]
    next_24h_rain = sum(row["rain_mm"] or 0.0 for row in next_rows)
    max_prob = max((row["rain_probability_pct"] or 0.0 for row in next_rows), default=0.0)
    current = min(rows, key=lambda row: abs((row["forecast_hour"] - now).total_seconds()))

    return WeatherContext(
        rain_last_24h_mm=round(last_24h_rain, 2),
        rain_forecast_next_24h_mm=round(next_24h_rain, 2),
        rain_probability_pct=round(max_prob, 1),
        temperature_c=current["temperature_c"],
        humidity_pct=current["humidity_pct"],
        wind_speed_kmh=current["wind_speed_kmh"],
        provider=provider_name,
        is_fallback_provider=False,
    )
