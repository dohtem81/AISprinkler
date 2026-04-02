"""Database bootstrap and seed helpers."""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import inspect, insert, select, text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.schema import CreateColumn

from aisprinkler.domain.value_objects.season import SeasonCode
from aisprinkler.infrastructure.persistence.db import get_engine
from aisprinkler.infrastructure.persistence.models import (
    Base,
    CurrentBaselineScheduleModel,
    DeviceModel,
    OriginalBaselineScheduleModel,
)


_DEFAULT_DEVICE_ID = uuid.UUID(
    os.getenv("DEVICE_ID", "00000000-0000-0000-0000-000000000001")
)
_DEFAULT_LOOKAHEAD_DAYS = int(os.getenv("BASELINE_LOOKAHEAD_DAYS", "7"))


def _baseline_templates() -> dict[SeasonCode, dict[str, Any]]:
    return {
        SeasonCode.SPRING: {
            "weekdays": {0, 2, 4},
            "start_time": time(6, 0),
            "duration_minutes": 15,
            "note": "Spring supplemental watering baseline.",
        },
        SeasonCode.SUMMER: {
            "weekdays": {0, 2, 4, 5},
            "start_time": time(5, 30),
            "duration_minutes": 25,
            "note": "Summer baseline for Alabama Bermuda grass.",
        },
        SeasonCode.FALL: {
            "weekdays": {0, 3},
            "start_time": time(6, 0),
            "duration_minutes": 15,
            "note": "Fall reduced watering baseline.",
        },
        SeasonCode.WINTER: {
            "weekdays": {0, 3},
            "start_time": time(6, 0),
            "duration_minutes": 10,
            "note": "Winter dormant-season baseline.",
        },
    }


def _sync_additive_schema(sync_conn: Any) -> None:
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue

        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.primary_key or column.name in existing_columns:
                continue
            ddl = str(CreateColumn(column).compile(dialect=sync_conn.dialect))
            sync_conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))


async def bootstrap_database() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_additive_schema)
        await _ensure_grafana_views(conn)
        await _ensure_default_device(conn)
        await _ensure_week_ahead_baselines(conn, _DEFAULT_DEVICE_ID, _DEFAULT_LOOKAHEAD_DAYS)


async def _ensure_grafana_views(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_schedule_timeline_v1 AS
            SELECT
                cbs.id AS schedule_id,
                cbs.device_id,
                d.name AS device_name,
                cbs.schedule_date,
                cbs.start_time,
                cbs.duration_minutes,
                cbs.source,
                cbs.is_active,
                cbs.superseded_at,
                (cbs.schedule_date::timestamp + cbs.start_time) AS schedule_start_local,
                (
                    cbs.schedule_date::timestamp
                    + cbs.start_time
                    + make_interval(mins => cbs.duration_minutes)
                ) AS schedule_end_local,
                CASE
                    WHEN cbs.is_active = true AND cbs.superseded_at IS NULL THEN 'active'
                    ELSE 'inactive'
                END AS state
            FROM current_baseline_schedule cbs
            JOIN device d ON d.id = cbs.device_id
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_llm_decisions_v1 AS
            SELECT
                ape.created_at AS event_time,
                ape.correlation_id,
                ape.run_id,
                ape.model_name,
                ape.model_version,
                ape.prompt_version,
                ape.policy_version,
                ape.response_payload ->> 'recommendation_action' AS decision,
                ape.response_payload ->> 'confidence_score' AS confidence_score,
                ape.response_payload ->> 'recommended_duration_minutes' AS recommended_duration_minutes,
                left(ape.response_payload ->> 'rationale', 240) AS rationale_summary
            FROM agent_prompt_exchange ape
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_weather_last_7d_v1 AS
            SELECT
                wfh.forecast_hour AS event_time,
                wl.zipcode,
                coalesce(wl.city, 'unknown') AS city,
                coalesce(wl.state_code, 'NA') AS state_code,
                wfh.provider,
                wfh.temperature_c,
                wfh.humidity_pct,
                wfh.rain_mm,
                wfh.rain_probability_pct,
                wfh.wind_speed_kmh,
                CASE
                    WHEN wfh.weather_code = '0' THEN 'sunny'
                    WHEN wfh.weather_code IN ('1', '2') THEN 'partly_cloudy'
                    ELSE 'cloudy'
                END AS sky_condition,
                wfh.is_observed
            FROM weather_forecast_hour wfh
            JOIN weather_location wl ON wl.id = wfh.location_id
            WHERE wfh.forecast_hour >= now() - interval '7 days'
              AND wfh.forecast_hour <= now()
              AND wfh.is_observed = true
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_weather_next_7d_v1 AS
            SELECT
                wfh.forecast_hour AS event_time,
                wl.zipcode,
                coalesce(wl.city, 'unknown') AS city,
                coalesce(wl.state_code, 'NA') AS state_code,
                wfh.provider,
                wfh.temperature_c,
                wfh.humidity_pct,
                wfh.rain_mm,
                wfh.rain_probability_pct,
                wfh.wind_speed_kmh,
                CASE
                    WHEN wfh.weather_code = '0' THEN 'sunny'
                    WHEN wfh.weather_code IN ('1', '2') THEN 'partly_cloudy'
                    ELSE 'cloudy'
                END AS sky_condition,
                wfh.is_observed
            FROM weather_forecast_hour wfh
            JOIN weather_location wl ON wl.id = wfh.location_id
            WHERE wfh.forecast_hour > now()
              AND wfh.forecast_hour <= now() + interval '7 days'
              AND wfh.is_observed = false
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_weather_next_24h_v1 AS
            SELECT
                wfh.forecast_hour AS event_time,
                wl.zipcode,
                coalesce(wl.city, 'unknown') AS city,
                coalesce(wl.state_code, 'NA') AS state_code,
                wfh.provider,
                wfh.temperature_c,
                wfh.humidity_pct,
                coalesce(wfh.rain_mm, 0) AS rain_mm,
                CASE
                    WHEN wfh.weather_code = '0' THEN 'sunny'
                    WHEN wfh.weather_code IN ('1', '2') THEN 'partly_cloudy'
                    ELSE 'cloudy'
                END AS sky_condition
            FROM weather_forecast_hour wfh
            JOIN weather_location wl ON wl.id = wfh.location_id
            WHERE wfh.forecast_hour > now()
              AND wfh.forecast_hour <= now() + interval '24 hours'
              AND wfh.is_observed = false
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_weather_next_7d_daily_v1 AS
            WITH hourly AS (
                SELECT
                    wfh.forecast_date,
                    wl.zipcode,
                    coalesce(wl.city, 'unknown') AS city,
                    coalesce(wl.state_code, 'NA') AS state_code,
                    wfh.provider,
                    wfh.temperature_c,
                    wfh.humidity_pct,
                    coalesce(wfh.rain_mm, 0) AS rain_mm,
                    CASE
                        WHEN wfh.weather_code = '0' THEN 'sunny'
                        WHEN wfh.weather_code IN ('1', '2') THEN 'partly_cloudy'
                        ELSE 'cloudy'
                    END AS sky_condition
                FROM weather_forecast_hour wfh
                JOIN weather_location wl ON wl.id = wfh.location_id
                WHERE wfh.forecast_hour > now()
                  AND wfh.forecast_hour <= now() + interval '7 days'
                  AND wfh.is_observed = false
            ),
            ranked AS (
                SELECT
                    forecast_date,
                    zipcode,
                    provider,
                    sky_condition,
                    count(*) AS samples,
                    row_number() OVER (
                        PARTITION BY forecast_date, zipcode, provider
                        ORDER BY count(*) DESC, sky_condition ASC
                    ) AS rn
                FROM hourly
                GROUP BY forecast_date, zipcode, provider, sky_condition
            )
            SELECT
                h.forecast_date::timestamp AS event_time,
                h.zipcode,
                h.city,
                h.state_code,
                h.provider,
                round(sum(h.rain_mm)::numeric, 2) AS rain_mm_day,
                round(avg(h.temperature_c)::numeric, 1) AS avg_temperature_c,
                round(avg(h.humidity_pct)::numeric, 1) AS avg_humidity_pct,
                r.sky_condition AS dominant_sky_condition
            FROM hourly h
            JOIN ranked r
              ON r.forecast_date = h.forecast_date
             AND r.zipcode = h.zipcode
             AND r.provider = h.provider
             AND r.rn = 1
            GROUP BY
                h.forecast_date,
                h.zipcode,
                h.city,
                h.state_code,
                h.provider,
                r.sky_condition
            ORDER BY h.forecast_date ASC
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_weather_given_day_v1 AS
            WITH hourly AS (
                SELECT
                    wfh.forecast_date,
                    wl.zipcode,
                    coalesce(wl.city, 'unknown') AS city,
                    coalesce(wl.state_code, 'NA') AS state_code,
                    wfh.provider,
                    wfh.is_observed,
                    wfh.temperature_c,
                    wfh.humidity_pct,
                    coalesce(wfh.rain_mm, 0) AS rain_mm,
                    CASE
                        WHEN wfh.weather_code = '0' THEN 'sunny'
                        WHEN wfh.weather_code IN ('1', '2') THEN 'partly_cloudy'
                        ELSE 'cloudy'
                    END AS sky_condition
                FROM weather_forecast_hour wfh
                JOIN weather_location wl ON wl.id = wfh.location_id
            ),
            ranked AS (
                SELECT
                    forecast_date,
                    zipcode,
                    provider,
                    is_observed,
                    sky_condition,
                    count(*) AS samples,
                    row_number() OVER (
                        PARTITION BY forecast_date, zipcode, provider, is_observed
                        ORDER BY count(*) DESC, sky_condition ASC
                    ) AS rn
                FROM hourly
                GROUP BY forecast_date, zipcode, provider, is_observed, sky_condition
            )
            SELECT
                h.forecast_date::timestamp AS event_time,
                h.zipcode,
                h.city,
                h.state_code,
                h.provider,
                h.is_observed,
                round(sum(h.rain_mm)::numeric, 2) AS rain_mm_day,
                round(avg(h.temperature_c)::numeric, 1) AS avg_temperature_c,
                round(avg(h.humidity_pct)::numeric, 1) AS avg_humidity_pct,
                r.sky_condition AS dominant_sky_condition
            FROM hourly h
            JOIN ranked r
              ON r.forecast_date = h.forecast_date
             AND r.zipcode = h.zipcode
             AND r.provider = h.provider
             AND r.is_observed = h.is_observed
             AND r.rn = 1
            GROUP BY
                h.forecast_date,
                h.zipcode,
                h.city,
                h.state_code,
                h.provider,
                h.is_observed,
                r.sky_condition
            ORDER BY h.forecast_date ASC
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_baseline_original_v1 AS
            SELECT
                obs.id AS schedule_id,
                obs.device_id,
                d.name AS device_name,
                obs.schedule_date,
                obs.start_time,
                obs.duration_minutes,
                obs.source,
                obs.is_active,
                (obs.schedule_date::timestamp + obs.start_time) AS schedule_start_local,
                (
                    obs.schedule_date::timestamp
                    + obs.start_time
                    + make_interval(mins => obs.duration_minutes)
                ) AS schedule_end_local,
                'original'::text AS schedule_kind
            FROM original_baseline_schedule obs
            JOIN device d ON d.id = obs.device_id
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW grafana_baseline_current_v1 AS
            SELECT
                cbs.id AS schedule_id,
                cbs.device_id,
                d.name AS device_name,
                cbs.schedule_date,
                cbs.start_time,
                cbs.duration_minutes,
                cbs.source,
                cbs.is_active,
                cbs.superseded_at,
                (cbs.schedule_date::timestamp + cbs.start_time) AS schedule_start_local,
                (
                    cbs.schedule_date::timestamp
                    + cbs.start_time
                    + make_interval(mins => cbs.duration_minutes)
                ) AS schedule_end_local,
                'current'::text AS schedule_kind
            FROM current_baseline_schedule cbs
            JOIN device d ON d.id = cbs.device_id
            """
        )
    )


async def _ensure_default_device(conn: AsyncConnection) -> None:
    stmt = select(DeviceModel.id).where(DeviceModel.id == _DEFAULT_DEVICE_ID)
    existing = (await conn.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return

    now = datetime.now(timezone.utc)
    await conn.execute(
        insert(DeviceModel).values(
            id=_DEFAULT_DEVICE_ID,
            name="Primary Lawn - Alabama",
            device_type="generic",
            timezone="America/Chicago",
            location_lat=32.3617,
            location_lon=-86.2792,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )


async def _ensure_week_ahead_baselines(
    conn: AsyncConnection,
    device_id: uuid.UUID,
    lookahead_days: int,
) -> None:
    start_date = date.today()
    end_date = start_date + timedelta(days=max(lookahead_days - 1, 0))
    expected_rows = await _build_expected_rows(conn, device_id, start_date, end_date)

    original_stmt = select(
        OriginalBaselineScheduleModel.id,
        OriginalBaselineScheduleModel.schedule_date,
        OriginalBaselineScheduleModel.start_time,
    ).where(
        OriginalBaselineScheduleModel.device_id == device_id,
        OriginalBaselineScheduleModel.schedule_date >= start_date,
        OriginalBaselineScheduleModel.schedule_date <= end_date,
        OriginalBaselineScheduleModel.is_active.is_(True),
    )
    current_stmt = select(
        CurrentBaselineScheduleModel.schedule_date,
        CurrentBaselineScheduleModel.start_time,
    ).where(
        CurrentBaselineScheduleModel.device_id == device_id,
        CurrentBaselineScheduleModel.schedule_date >= start_date,
        CurrentBaselineScheduleModel.schedule_date <= end_date,
        CurrentBaselineScheduleModel.is_active.is_(True),
        CurrentBaselineScheduleModel.superseded_at.is_(None),
    )

    existing_original = {
        (row.schedule_date, row.start_time): row.id
        for row in (await conn.execute(original_stmt)).all()
    }
    existing_current = {
        (row.schedule_date, row.start_time)
        for row in (await conn.execute(current_stmt)).all()
    }

    now = datetime.now(timezone.utc)
    new_original_rows: list[dict[str, Any]] = []
    new_current_rows: list[dict[str, Any]] = []

    for row in expected_rows:
        key = (row["schedule_date"], row["start_time"])
        original_id = existing_original.get(key)
        if original_id is None:
            original_id = uuid.uuid4()
            existing_original[key] = original_id
            new_original_rows.append(
                {
                    "id": original_id,
                    "device_id": device_id,
                    "schedule_date": row["schedule_date"],
                    "grass_type": row["grass_type"],
                    "start_time": row["start_time"],
                    "duration_minutes": row["duration_minutes"],
                    "is_active": True,
                    "notes": row["notes"],
                    "source": row["source"],
                    "created_at": now,
                    "updated_at": now,
                }
            )

        if key not in existing_current:
            new_current_rows.append(
                {
                    "id": uuid.uuid4(),
                    "device_id": device_id,
                    "original_schedule_id": original_id,
                    "schedule_date": row["schedule_date"],
                    "grass_type": row["grass_type"],
                    "start_time": row["start_time"],
                    "duration_minutes": row["duration_minutes"],
                    "is_active": True,
                    "notes": row["notes"],
                    "source": row["source"],
                    "superseded_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    if new_original_rows:
        await conn.execute(insert(OriginalBaselineScheduleModel), new_original_rows)
    if new_current_rows:
        await conn.execute(insert(CurrentBaselineScheduleModel), new_current_rows)


async def _build_expected_rows(
    conn: AsyncConnection,
    device_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    legacy_rows = await _load_legacy_templates(conn, device_id)
    if legacy_rows:
        return _expand_legacy_rows(legacy_rows, start_date, end_date)
    return _build_default_rows(start_date, end_date)


async def _load_legacy_templates(
    conn: AsyncConnection,
    device_id: uuid.UUID,
) -> list[dict[str, Any]]:
    table_exists = await conn.run_sync(
        lambda sync_conn: "baseline_schedule" in inspect(sync_conn).get_table_names()
    )
    if not table_exists:
        return []

    result = await conn.execute(
        text(
            """
            SELECT day_of_week, season_code, effective_month_start, effective_month_end,
                   grass_type, start_time, duration_minutes, notes
            FROM baseline_schedule
            WHERE device_id = :device_id AND is_active = true
            """
        ),
        {"device_id": device_id},
    )
    return [dict(row._mapping) for row in result]


def _expand_legacy_rows(
    legacy_rows: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_date = start_date
    while current_date <= end_date:
        for template in legacy_rows:
            if _legacy_template_matches(template, current_date):
                rows.append(
                    {
                        "schedule_date": current_date,
                        "grass_type": template.get("grass_type"),
                        "start_time": template["start_time"],
                        "duration_minutes": template["duration_minutes"],
                        "notes": template.get("notes") or "Migrated from legacy baseline_schedule.",
                        "source": "legacy_migration",
                    }
                )
        current_date += timedelta(days=1)
    return rows


def _legacy_template_matches(template: dict[str, Any], schedule_date: date) -> bool:
    if template["day_of_week"] != schedule_date.weekday():
        return False

    month = schedule_date.month
    start_month = template["effective_month_start"]
    end_month = template["effective_month_end"]
    if end_month < start_month:
        month_matches = month >= start_month or month <= end_month
    else:
        month_matches = start_month <= month <= end_month
    if not month_matches:
        return False

    season_code = template["season_code"]
    return season_code == "all" or season_code == SeasonCode.from_month(month).value


def _build_default_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    templates = _baseline_templates()
    current_date = start_date
    while current_date <= end_date:
        season = SeasonCode.from_month(current_date.month)
        template = templates[season]
        if current_date.weekday() in template["weekdays"]:
            rows.append(
                {
                    "schedule_date": current_date,
                    "grass_type": "bermuda",
                    "start_time": template["start_time"],
                    "duration_minutes": template["duration_minutes"],
                    "notes": template["note"],
                    "source": "startup_seed",
                }
            )
        current_date += timedelta(days=1)
    return rows