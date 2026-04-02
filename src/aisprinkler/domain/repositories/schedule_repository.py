"""Schedule repository interface (domain port)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from aisprinkler.domain.entities.baseline_schedule import BaselineKind, BaselineSchedule


class ScheduleRepository(ABC):
    @abstractmethod
    async def get_active_for_date(
        self, device_id: UUID, run_date: date
    ) -> list[BaselineSchedule]:
        """Return current active baseline rows for a specific calendar date."""
        ...

    @abstractmethod
    async def save(self, schedule: BaselineSchedule) -> None: ...

    @abstractmethod
    async def deactivate(self, schedule_id: UUID) -> None: ...

    @abstractmethod
    async def list_for_range(
        self,
        device_id: UUID,
        start_date: date,
        end_date: date,
        *,
        baseline_kind: BaselineKind | None = None,
        include_history: bool = False,
    ) -> list[BaselineSchedule]: ...
