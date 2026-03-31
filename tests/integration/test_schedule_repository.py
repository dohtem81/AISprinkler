"""Integration tests for SqlAlchemyScheduleRepository.

Requires: running PostgreSQL (provided by Testcontainers via conftest.py).
"""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.domain.entities.baseline_schedule import BaselineSchedule  # noqa: E501
from aisprinkler.domain.value_objects.season import SeasonCode
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
        day_of_week=0,  # Monday
        season_code=SeasonCode.SUMMER,
        effective_month_start=5,
        effective_month_end=9,
        start_time=time(5, 30),
        duration_minutes=25,
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

    async def test_no_result_for_wrong_season(
        self, repo: SqlAlchemyScheduleRepository, device_id: uuid.UUID
    ) -> None:
        schedule = _summer_monday(device_id)
        await repo.save(schedule)

        monday_in_january = date(2026, 1, 5)  # Monday, January → winter
        results = await repo.get_active_for_date(device_id, monday_in_january)

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
