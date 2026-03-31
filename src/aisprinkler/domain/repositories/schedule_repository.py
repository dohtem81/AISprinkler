"""Schedule repository interface (domain port)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from aisprinkler.domain.entities.baseline_schedule import BaselineSchedule


class ScheduleRepository(ABC):
    @abstractmethod
    async def get_active_for_date(
        self, device_id: UUID, run_date: date
    ) -> list[BaselineSchedule]:
        """Return all active baseline rows that apply for the given date's weekday and season."""
        ...

    @abstractmethod
    async def save(self, schedule: BaselineSchedule) -> None: ...

    @abstractmethod
    async def deactivate(self, schedule_id: UUID) -> None: ...
