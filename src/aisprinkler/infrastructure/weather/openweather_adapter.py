"""OpenWeatherMap adapter – implements WeatherPort.

This is a stub implementation.  The actual HTTP logic is intentionally left
as a TODO so that API key handling and response mapping can be implemented
once the weather provider contract is finalized.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import httpx

from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.domain.value_objects.weather_context import WeatherContext


class OpenWeatherAdapter(WeatherPort):
    """Calls the OpenWeatherMap One Call API 3.0."""

    BASE_URL = "https://api.openweathermap.org/data/3.0/onecall"

    def __init__(self, api_key: str, lat: float, lon: float) -> None:
        self._api_key = api_key
        self._lat = lat
        self._lon = lon

    async def get_weather_context(
        self, device_id: UUID, as_of: datetime
    ) -> WeatherContext:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.BASE_URL,
                params={
                    "lat": self._lat,
                    "lon": self._lon,
                    "exclude": "minutely,hourly,alerts",
                    "appid": self._api_key,
                    "units": "metric",
                },
            )
            response.raise_for_status()
            data = response.json()

        current = data.get("current", {})
        daily = data.get("daily", [{}])
        today = daily[0] if daily else {}

        return WeatherContext(
            rain_last_24h_mm=current.get("rain", {}).get("1h", 0.0) * 24,
            rain_forecast_next_24h_mm=today.get("rain", 0.0),
            rain_probability_pct=today.get("pop", 0.0) * 100,
            temperature_c=current.get("temp"),
            humidity_pct=current.get("humidity"),
            wind_speed_kmh=(current.get("wind_speed", 0.0) * 3.6),
            provider="openweathermap",
            is_fallback_provider=False,
        )
