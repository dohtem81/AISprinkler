"""Weather persistence adapter for location and hourly forecast/history rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.infrastructure.persistence.models import (
    WeatherForecastHourModel,
    WeatherLocationModel,
)


class WeatherRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_location(
        self,
        zipcode: str,
        lat: float,
        lon: float,
        city: str | None = None,
        state_code: str | None = None,
        country_code: str = "US",
    ) -> uuid.UUID:
        stmt = select(WeatherLocationModel.id).where(WeatherLocationModel.zipcode == zipcode)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc)
        model = WeatherLocationModel(
            id=uuid.uuid4(),
            zipcode=zipcode,
            city=city,
            state_code=state_code,
            country_code=country_code,
            location_lat=lat,
            location_lon=lon,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return model.id

    async def upsert_hourly_rows(
        self, location_id: uuid.UUID, rows: list[dict[str, Any]]
    ) -> int:
        if not rows:
            return 0

        now = datetime.now(timezone.utc)

        # Forecast pulls should replace the entire future window so stale
        # values are not left behind after provider updates.
        forecast_providers = {
            str(row.get("provider", "open_meteo"))
            for row in rows
            if not bool(row.get("is_observed", False))
        }
        for provider in forecast_providers:
            await self._session.execute(
                delete(WeatherForecastHourModel).where(
                    WeatherForecastHourModel.location_id == location_id,
                    WeatherForecastHourModel.provider == provider,
                    WeatherForecastHourModel.is_observed.is_(False),
                    WeatherForecastHourModel.forecast_hour >= now,
                )
            )

        payload = [
            {
                "id": uuid.uuid4(),
                "location_id": location_id,
                "forecast_date": row["forecast_date"],
                "forecast_hour": row["forecast_hour"],
                "temperature_c": row.get("temperature_c"),
                "feels_like_c": row.get("feels_like_c"),
                "humidity_pct": row.get("humidity_pct"),
                "rain_mm": row.get("rain_mm"),
                "snow_mm": row.get("snow_mm"),
                "rain_probability_pct": row.get("rain_probability_pct"),
                "wind_speed_kmh": row.get("wind_speed_kmh"),
                "wind_direction_deg": row.get("wind_direction_deg"),
                "weather_code": row.get("weather_code"),
                "weather_description": row.get("weather_description"),
                "is_observed": row.get("is_observed", False),
                "provider": row.get("provider", "open_meteo"),
                "fetched_at": now,
                "created_at": now,
            }
            for row in rows
        ]

        insert_stmt = pg_insert(WeatherForecastHourModel).values(payload)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_weather_forecast_hour_location_hour_provider",
            set_={
                "temperature_c": insert_stmt.excluded.temperature_c,
                "feels_like_c": insert_stmt.excluded.feels_like_c,
                "humidity_pct": insert_stmt.excluded.humidity_pct,
                "rain_mm": insert_stmt.excluded.rain_mm,
                "snow_mm": insert_stmt.excluded.snow_mm,
                "rain_probability_pct": insert_stmt.excluded.rain_probability_pct,
                "wind_speed_kmh": insert_stmt.excluded.wind_speed_kmh,
                "wind_direction_deg": insert_stmt.excluded.wind_direction_deg,
                "weather_code": insert_stmt.excluded.weather_code,
                "weather_description": insert_stmt.excluded.weather_description,
                "is_observed": insert_stmt.excluded.is_observed,
                "fetched_at": insert_stmt.excluded.fetched_at,
            },
        )
        await self._session.execute(upsert_stmt)
        return len(payload)
