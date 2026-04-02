#!/usr/bin/env python
"""Create baseline schedules for the last N days (default 30).

The script is non-destructive:
- Inserts missing rows into original_baseline_schedule.
- Inserts missing active rows into current_baseline_schedule.
- Does not overwrite existing active/current rows.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from aisprinkler.infrastructure.persistence.bootstrap import bootstrap_database
from aisprinkler.infrastructure.persistence.db import get_session_factory
from aisprinkler.infrastructure.persistence.models import (
    CurrentBaselineScheduleModel,
    OriginalBaselineScheduleModel,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _template_for_day(day: date) -> tuple[time, int, str] | None:
    month = day.month
    weekday = day.weekday()  # 0=Mon .. 6=Sun

    if month in (3, 4):  # spring
        if weekday in (0, 2, 4):
            return time(6, 0), 15, "Spring supplemental watering baseline."
        return None

    if 5 <= month <= 9:  # summer
        if weekday in (0, 2, 4, 5):
            return time(5, 30), 25, "Summer baseline for Alabama Bermuda grass."
        return None

    if month in (10, 11):  # fall
        if weekday in (0, 3):
            return time(6, 0), 15, "Fall reduced watering baseline."
        return None

    # winter
    if weekday in (0, 3):
        return time(6, 0), 10, "Winter dormant-season baseline."
    return None


async def main() -> None:
    device_id_raw = os.getenv("DEVICE_ID", "00000000-0000-0000-0000-000000000001")
    try:
        device_id = uuid.UUID(device_id_raw)
    except ValueError:
        logger.error("Invalid DEVICE_ID: %s", device_id_raw)
        sys.exit(1)

    days_back = int(os.getenv("BASELINE_HISTORY_DAYS", "30"))
    if days_back <= 0:
        logger.error("BASELINE_HISTORY_DAYS must be > 0")
        sys.exit(1)

    end_day = date.today()
    start_day = end_day - timedelta(days=days_back - 1)

    logger.info(
        "Creating baseline history: device=%s start=%s end=%s days=%s",
        device_id,
        start_day,
        end_day,
        days_back,
    )

    await bootstrap_database()

    inserted_original = 0
    inserted_current = 0

    session_factory = get_session_factory()
    async with session_factory() as session:
        day = start_day
        while day <= end_day:
            template = _template_for_day(day)
            if template is None:
                day += timedelta(days=1)
                continue

            start_time, duration_minutes, notes = template

            original_stmt = select(OriginalBaselineScheduleModel).where(
                OriginalBaselineScheduleModel.device_id == device_id,
                OriginalBaselineScheduleModel.schedule_date == day,
                OriginalBaselineScheduleModel.start_time == start_time,
            )
            original = (await session.execute(original_stmt)).scalars().first()
            if original is None:
                now = datetime.now(timezone.utc)
                original = OriginalBaselineScheduleModel(
                    id=uuid.uuid4(),
                    device_id=device_id,
                    schedule_date=day,
                    grass_type="bermuda",
                    start_time=start_time,
                    duration_minutes=duration_minutes,
                    is_active=True,
                    notes=notes,
                    source="history_seed",
                    created_at=now,
                    updated_at=now,
                )
                session.add(original)
                await session.flush()
                inserted_original += 1

            current_stmt = select(CurrentBaselineScheduleModel).where(
                CurrentBaselineScheduleModel.device_id == device_id,
                CurrentBaselineScheduleModel.schedule_date == day,
                CurrentBaselineScheduleModel.start_time == start_time,
                CurrentBaselineScheduleModel.is_active.is_(True),
                CurrentBaselineScheduleModel.superseded_at.is_(None),
            )
            current = (await session.execute(current_stmt)).scalars().first()
            if current is None:
                now = datetime.now(timezone.utc)
                session.add(
                    CurrentBaselineScheduleModel(
                        id=uuid.uuid4(),
                        device_id=device_id,
                        original_schedule_id=original.id,
                        schedule_date=day,
                        grass_type="bermuda",
                        start_time=start_time,
                        duration_minutes=duration_minutes,
                        is_active=True,
                        notes=notes,
                        source="history_seed",
                        superseded_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                inserted_current += 1

            day += timedelta(days=1)

        await session.commit()

    logger.info(
        "Baseline history complete: inserted_original=%s inserted_current=%s",
        inserted_original,
        inserted_current,
    )


if __name__ == "__main__":
    asyncio.run(main())
