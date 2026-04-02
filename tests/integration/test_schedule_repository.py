"""Integration tests for SqlAlchemyScheduleRepository.

Requires: running PostgreSQL (provided by Testcontainers via conftest.py).
"""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.domain.entities.baseline_schedule import BaselineKind, BaselineSchedule
from aisprinkler.infrastructure.persistence.schedule_repo import (
    SqlAlchemyScheduleRepository,
)


@pytest.fixture()
def repo(db_session: AsyncSession) -> SqlAlchemyScheduleRepository:
    return SqlAlchemyScheduleRepository(db_session)


@pytest.fixture()
def device_id(device_in_db: uuid.UUID) -> uuid.UUID:
    """Use a DB-backed device_id so that FK on baseline_schedule.device_id is satisfied."""
    return device_in_db


def _summer_monday(device_id: uuid.UUID) -> BaselineSchedule:
    return BaselineSchedule(
        device_id=device_id,
        schedule_date=date(2026, 7, 6),
        start_time=time(5, 30),
        duration_minutes=25,
        baseline_kind=BaselineKind.CURRENT,
        grass_type="bermuda",
    )


class TestGetActiveForDate:
    async def test_returns_matching_schedule(
        self, repo: SqlAlchemyScheduleRepository, device_id: uuid.UUID
    ) -> None:
        schedule = _summer_monday(device_id)
        await repo.save(schedule)

        monday_in_july = date(2026, 7, 6)  # Monday, July
        results = await repo.get_active_for_date(device_id, monday_in_july)

        assert len(results) == 1
        assert results[0].duration_minutes == 25

    async def test_no_result_for_wrong_date(
        self, repo: SqlAlchemyScheduleRepository, device_id: uuid.UUID
    ) -> None:
        schedule = _summer_monday(device_id)
        await repo.save(schedule)

        next_day = date(2026, 7, 7)
        results = await repo.get_active_for_date(device_id, next_day)

        assert results == []

    async def test_no_result_for_inactive_schedule(
        self, repo: SqlAlchemyScheduleRepository, device_id: uuid.UUID
    ) -> None:
        schedule = _summer_monday(device_id)
        schedule.is_active = False
        await repo.save(schedule)

        monday_in_july = date(2026, 7, 6)
        results = await repo.get_active_for_date(device_id, monday_in_july)

        assert results == []

    async def test_range_query_returns_original_and_current(
        self, repo: SqlAlchemyScheduleRepository, device_id: uuid.UUID
    ) -> None:
        schedule_date = date(2026, 7, 6)
        await repo.save(
            BaselineSchedule(
                device_id=device_id,
                schedule_date=schedule_date,
                start_time=time(5, 30),
                duration_minutes=25,
                baseline_kind=BaselineKind.ORIGINAL,
                grass_type="bermuda",
            )
        )
        await repo.save(
            BaselineSchedule(
                device_id=device_id,
                schedule_date=schedule_date,
                start_time=time(5, 30),
                duration_minutes=20,
                baseline_kind=BaselineKind.CURRENT,
                grass_type="bermuda",
            )
        )

        results = await repo.list_for_range(device_id, schedule_date, schedule_date)

        assert len(results) == 2
