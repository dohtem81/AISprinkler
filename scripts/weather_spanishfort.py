#!/usr/bin/env python
"""Backfill hourly weather history into DB using Open-Meteo archive.

Run via Docker:
  docker compose -f docker/docker-compose.yml run --rm app python scripts/weather_spanishfort.py

Environment parameters:
  HISTORY_DAYS   default: 30
  WEATHER_LAT    default: 30.676
  WEATHER_LON    default: -87.914
  WEATHER_ZIPCODE default: 36527
  WEATHER_CITY   default: Spanish Fort
  WEATHER_STATE  default: AL
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta

from aisprinkler.infrastructure.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    days_back = int(os.getenv("HISTORY_DAYS", "30"))
    lat = float(os.getenv("WEATHER_LAT", "30.676"))
    lon = float(os.getenv("WEATHER_LON", "-87.914"))
    zipcode = os.getenv("WEATHER_ZIPCODE", "36527")
    city = os.getenv("WEATHER_CITY", "Spanish Fort")
    state_code = os.getenv("WEATHER_STATE", "AL")

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=max(days_back - 1, 0))

    logger.info(
        "Starting weather history backfill",
        extra={
            "action": "weather_pull",
            "component": "weather",
            "location": "spanish_fort_al",
            "weather_provider": "open_meteo",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "zipcode": zipcode,
            "city": city,
            "state": state_code,
        },
    )

    from aisprinkler.infrastructure.persistence.bootstrap import bootstrap_database
    from aisprinkler.infrastructure.persistence.db import get_session_factory
    from aisprinkler.infrastructure.persistence.weather_repo import WeatherRepository
    from aisprinkler.infrastructure.weather.open_meteo_adapter import OpenMeteoAdapter

    logger.info(
        "Syncing database schema and Grafana views before import",
        extra={
            "action": "db_bootstrap",
            "component": "persistence",
            "status": "start",
        },
    )
    await bootstrap_database()
    logger.info(
        "Database schema and Grafana views synchronized",
        extra={
            "action": "db_bootstrap",
            "component": "persistence",
            "status": "success",
        },
    )

    try:
        adapter = OpenMeteoAdapter(lat=lat, lon=lon)
        rows = await adapter.fetch_history_hours(start_date=start_date, end_date=end_date)

        session_factory = get_session_factory()
        async with session_factory() as session:
            weather_repo = WeatherRepository(session)
            location_id = await weather_repo.get_or_create_location(
                zipcode=zipcode,
                lat=lat,
                lon=lon,
                city=city,
                state_code=state_code,
            )
            count = await weather_repo.upsert_hourly_rows(location_id, rows)
            await session.commit()
    except Exception:
        logger.exception(
            "Weather history backfill failed",
            extra={
                "action": "weather_pull",
                "component": "weather",
                "location": "spanish_fort_al",
                "weather_provider": "open_meteo",
                "status": "failure",
            },
        )
        raise

    logger.info(
        "Weather history backfill completed",
        extra={
            "action": "weather_pull",
            "component": "weather",
            "location": "spanish_fort_al",
            "weather_provider": "open_meteo",
            "status": "success",
            "rows_fetched": len(rows),
            "rows_persisted": count,
        },
    )


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())