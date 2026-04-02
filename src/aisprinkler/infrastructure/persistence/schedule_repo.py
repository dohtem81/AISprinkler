"""SQLAlchemy implementation of ScheduleRepository."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.domain.entities.baseline_schedule import BaselineKind, BaselineSchedule
from aisprinkler.domain.repositories.schedule_repository import ScheduleRepository
from aisprinkler.infrastructure.persistence.models import (
    CurrentBaselineScheduleModel,
    OriginalBaselineScheduleModel,
)


class SqlAlchemyScheduleRepository(ScheduleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_date(
        self, device_id: UUID, run_date: date
    ) -> list[BaselineSchedule]:
        stmt = (
            select(CurrentBaselineScheduleModel)
            .where(
                CurrentBaselineScheduleModel.device_id == device_id,
                CurrentBaselineScheduleModel.schedule_date == run_date,
                CurrentBaselineScheduleModel.is_active.is_(True),
                CurrentBaselineScheduleModel.superseded_at.is_(None),
            )
            .order_by(CurrentBaselineScheduleModel.start_time.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_current_entity(r) for r in rows]

    async def save(self, schedule: BaselineSchedule) -> None:
        if schedule.baseline_kind is BaselineKind.CURRENT:
            await self._supersede_visible_current(schedule)
            model = self._to_current_model(schedule)
        else:
            model = self._to_original_model(schedule)
        self._session.add(model)
        await self._session.flush()

    async def deactivate(self, schedule_id: UUID) -> None:
        result = await self._session.get(CurrentBaselineScheduleModel, schedule_id)
        if result is not None:
            result.is_active = False
            result.superseded_at = datetime.now(timezone.utc)
            await self._session.flush()
            return

        original = await self._session.get(OriginalBaselineScheduleModel, schedule_id)
        if original is not None:
            original.is_active = False
            await self._session.flush()

    async def list_for_range(
        self,
        device_id: UUID,
        start_date: date,
        end_date: date,
        *,
        baseline_kind: BaselineKind | None = None,
        include_history: bool = False,
    ) -> list[BaselineSchedule]:
        rows: list[BaselineSchedule] = []
        if baseline_kind in (None, BaselineKind.ORIGINAL):
            original_stmt = (
                select(OriginalBaselineScheduleModel)
                .where(
                    OriginalBaselineScheduleModel.device_id == device_id,
                    OriginalBaselineScheduleModel.schedule_date >= start_date,
                    OriginalBaselineScheduleModel.schedule_date <= end_date,
                )
                .order_by(
                    OriginalBaselineScheduleModel.schedule_date.asc(),
                    OriginalBaselineScheduleModel.start_time.asc(),
                )
            )
            if not include_history:
                original_stmt = original_stmt.where(OriginalBaselineScheduleModel.is_active.is_(True))
            rows.extend(
                self._to_original_entity(row)
                for row in (await self._session.execute(original_stmt)).scalars().all()
            )

        if baseline_kind in (None, BaselineKind.CURRENT):
            current_stmt = (
                select(CurrentBaselineScheduleModel)
                .where(
                    CurrentBaselineScheduleModel.device_id == device_id,
                    CurrentBaselineScheduleModel.schedule_date >= start_date,
                    CurrentBaselineScheduleModel.schedule_date <= end_date,
                )
                .order_by(
                    CurrentBaselineScheduleModel.schedule_date.asc(),
                    CurrentBaselineScheduleModel.start_time.asc(),
                    CurrentBaselineScheduleModel.created_at.asc(),
                )
            )
            if not include_history:
                current_stmt = current_stmt.where(
                    CurrentBaselineScheduleModel.is_active.is_(True),
                    CurrentBaselineScheduleModel.superseded_at.is_(None),
                )
            rows.extend(
                self._to_current_entity(row)
                for row in (await self._session.execute(current_stmt)).scalars().all()
            )

        return sorted(rows, key=lambda item: (item.schedule_date, item.start_time, item.created_at))

    async def _supersede_visible_current(self, schedule: BaselineSchedule) -> None:
        stmt = select(CurrentBaselineScheduleModel).where(
            CurrentBaselineScheduleModel.device_id == schedule.device_id,
            CurrentBaselineScheduleModel.schedule_date == schedule.schedule_date,
            CurrentBaselineScheduleModel.start_time == schedule.start_time,
            CurrentBaselineScheduleModel.is_active.is_(True),
            CurrentBaselineScheduleModel.superseded_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        if not rows:
            return

        now = datetime.now(timezone.utc)
        for row in rows:
            row.is_active = False
            row.superseded_at = now
            row.updated_at = now
        await self._session.flush()

    # ── Mapping helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _to_original_entity(m: OriginalBaselineScheduleModel) -> BaselineSchedule:
        return BaselineSchedule(
            id=m.id,
            device_id=m.device_id,
            schedule_date=m.schedule_date,
            start_time=m.start_time,
            duration_minutes=m.duration_minutes,
            baseline_kind=BaselineKind.ORIGINAL,
            is_active=m.is_active,
            grass_type=m.grass_type,
            notes=m.notes,
            source=m.source,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _to_current_entity(m: CurrentBaselineScheduleModel) -> BaselineSchedule:
        return BaselineSchedule(
            id=m.id,
            device_id=m.device_id,
            schedule_date=m.schedule_date,
            start_time=m.start_time,
            duration_minutes=m.duration_minutes,
            baseline_kind=BaselineKind.CURRENT,
            is_active=m.is_active,
            grass_type=m.grass_type,
            notes=m.notes,
            source=m.source,
            original_schedule_id=m.original_schedule_id,
            superseded_at=m.superseded_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _to_original_model(e: BaselineSchedule) -> OriginalBaselineScheduleModel:
        return OriginalBaselineScheduleModel(
            id=e.id,
            device_id=e.device_id,
            schedule_date=e.schedule_date,
            start_time=e.start_time,
            duration_minutes=e.duration_minutes,
            is_active=e.is_active,
            grass_type=e.grass_type,
            notes=e.notes,
            source=e.source,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )

    @staticmethod
    def _to_current_model(e: BaselineSchedule) -> CurrentBaselineScheduleModel:
        return CurrentBaselineScheduleModel(
            id=e.id,
            device_id=e.device_id,
            original_schedule_id=e.original_schedule_id,
            schedule_date=e.schedule_date,
            start_time=e.start_time,
            duration_minutes=e.duration_minutes,
            is_active=e.is_active,
            grass_type=e.grass_type,
            notes=e.notes,
            source=e.source,
            superseded_at=e.superseded_at,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
