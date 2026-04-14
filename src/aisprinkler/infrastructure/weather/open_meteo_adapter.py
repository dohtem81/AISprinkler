"""Open-Meteo adapter – implements WeatherPort using the free Open-Meteo API."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.domain.value_objects.weather_context import WeatherContext
from aisprinkler.infrastructure.weather.forecast_refresh import (
    ForecastRefreshPort,
    build_weather_context_from_rows,
)

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_HISTORY_URL = "https://archive-api.open-meteo.com/v1/archive"

_FORECAST_HOURLY = (
    "temperature_2m,relative_humidity_2m,precipitation_probability,"
    "precipitation,rain,snowfall,weather_code,wind_speed_10m,wind_direction_10m"
)
_HISTORY_HOURLY = (
    "temperature_2m,relative_humidity_2m,precipitation,"
    "rain,snowfall,weather_code,wind_speed_10m,wind_direction_10m"
)
_PROVIDER_NAME = "open_meteo"


class OpenMeteoAdapter(WeatherPort, ForecastRefreshPort):
    """Open-Meteo implementation for forecast and history retrieval."""

    def __init__(self, lat: float, lon: float, timeout: float = 15.0) -> None:
        self._lat = lat
        self._lon = lon
        self._timeout = timeout
        self._location_label = os.getenv("WEATHER_LOCATION_LABEL", "spanish_fort_al")

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def get_weather_context(
        self, device_id: UUID, as_of: datetime
    ) -> WeatherContext:
        rows = await self.fetch_forecast_hours(days=7)
        context = self.build_context_from_rows(rows, as_of)
        logger.info(
            "Built weather context",
            extra={
                "action": "weather_context_build",
                "component": "weather",
                "location": self._location_label,
                "weather_provider": self.provider_name,
                "device_id": str(device_id),
                "rows_used": len(rows),
                "rain_forecast_next_24h_mm": context.rain_forecast_next_24h_mm,
                "rain_probability_pct": context.rain_probability_pct,
            },
        )
        return context

    async def fetch_forecast_hours(self, days: int = 7) -> list[dict[str, Any]]:
        logger.info(
            "Fetching forecast hours",
            extra={
                "action": "weather_pull",
                "component": "weather",
                "location": self._location_label,
                "weather_provider": self.provider_name,
                "pull_kind": "forecast",
                "days": days,
            },
        )
        try:
            data = await self._fetch_forecast(days=days)
            rows = _parse_hourly_rows(data, is_observed=False)
        except Exception:
            logger.exception(
                "Forecast pull failed",
                extra={
                    "action": "weather_pull",
                    "component": "weather",
                    "location": self._location_label,
                    "weather_provider": self.provider_name,
                    "pull_kind": "forecast",
                    "status": "failure",
                },
            )
            raise

        logger.info(
            "Forecast pull completed",
            extra={
                "action": "weather_pull",
                "component": "weather",
                "location": self._location_label,
                "weather_provider": self.provider_name,
                "pull_kind": "forecast",
                "status": "success",
                "rows_fetched": len(rows),
            },
        )
        return rows

    async def fetch_history_hours(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        logger.info(
            "Fetching history hours",
            extra={
                "action": "weather_pull",
                "component": "weather",
                "location": self._location_label,
                "weather_provider": self.provider_name,
                "pull_kind": "history",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        try:
            data = await self._fetch_history(start_date, end_date)
            rows = _parse_hourly_rows(data, is_observed=True)
        except Exception:
            logger.exception(
                "History pull failed",
                extra={
                    "action": "weather_pull",
                    "component": "weather",
                    "location": self._location_label,
                    "weather_provider": self.provider_name,
                    "pull_kind": "history",
                    "status": "failure",
                },
            )
            raise

        logger.info(
            "History pull completed",
            extra={
                "action": "weather_pull",
                "component": "weather",
                "location": self._location_label,
                "weather_provider": self.provider_name,
                "pull_kind": "history",
                "status": "success",
                "rows_fetched": len(rows),
            },
        )
        return rows

    async def _fetch_forecast(self, days: int) -> dict[str, Any]:
        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "hourly": _FORECAST_HOURLY,
            "forecast_days": days,
            "timezone": "UTC",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_FORECAST_URL, params=params)
            resp.raise_for_status()
        return resp.json()

    async def _fetch_history(self, start_date: date, end_date: date) -> dict[str, Any]:
        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "hourly": _HISTORY_HOURLY,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": "UTC",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_HISTORY_URL, params=params)
            resp.raise_for_status()
        return resp.json()

    @staticmethod
    def build_context_from_rows(
        rows: list[dict[str, Any]],
        as_of: datetime,
    ) -> WeatherContext:
        return build_weather_context_from_rows(
            rows,
            as_of,
            provider_name=_PROVIDER_NAME,
        )


def _parse_hourly_rows(
    data: dict[str, Any], *, is_observed: bool
) -> list[dict[str, Any]]:
    hourly = data.get("hourly", {})
    times: list[str] = hourly.get("time", [])

    def _value(key: str, idx: int) -> Any:
        series = hourly.get(key, [])
        return series[idx] if idx < len(series) else None

    rows: list[dict[str, Any]] = []
    for idx, raw_time in enumerate(times):
        forecast_hour = datetime.fromisoformat(raw_time).replace(tzinfo=timezone.utc)
        rows.append(
            {
                "forecast_date": forecast_hour.date(),
                "forecast_hour": forecast_hour,
                "temperature_c": _value("temperature_2m", idx),
                "feels_like_c": None,
                "humidity_pct": _value("relative_humidity_2m", idx),
                "rain_mm": _value("rain", idx),
                "snow_mm": _value("snowfall", idx),
                "rain_probability_pct": _value("precipitation_probability", idx),
                "wind_speed_kmh": _value("wind_speed_10m", idx),
                "wind_direction_deg": _value("wind_direction_10m", idx),
                "weather_code": str(_value("weather_code", idx))
                if _value("weather_code", idx) is not None
                else None,
                "weather_description": None,
                "is_observed": is_observed,
                "provider": _PROVIDER_NAME,
            }
        )
    return rows
