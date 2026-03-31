"""WeatherContext value object – normalised inputs for the AI decision agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherContext:
    """Immutable snapshot of weather data used in a single adjustment run.

    All precipitation values are in millimetres.
    probability fields are in the range [0.0, 100.0].
    """

    rain_last_24h_mm: float
    rain_forecast_next_24h_mm: float
    rain_probability_pct: float
    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    provider: str = "unknown"
    is_fallback_provider: bool = False

    def is_heavy_rain_observed(self, threshold_mm: float = 10.0) -> bool:
        return self.rain_last_24h_mm >= threshold_mm

    def is_high_rain_forecast(self, threshold_mm: float = 8.0) -> bool:
        return self.rain_forecast_next_24h_mm >= threshold_mm

    def is_high_rain_probability(self, threshold_pct: float = 60.0) -> bool:
        return self.rain_probability_pct >= threshold_pct
