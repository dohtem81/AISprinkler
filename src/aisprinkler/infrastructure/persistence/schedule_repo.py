"""SQLAlchemy implementation of ScheduleRepository."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.domain.entities.baseline_schedule import BaselineSchedule
from aisprinkler.domain.repositories.schedule_repository import ScheduleRepository
from aisprinkler.domain.value_objects.season import SeasonCode
from aisprinkler.infrastructure.persistence.models import BaselineScheduleModel


class SqlAlchemyScheduleRepository(ScheduleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_date(
        self, device_id: UUID, run_date: date
    ) -> list[BaselineSchedule]:
        weekday = run_date.weekday()  # 0=Monday … 6=Sunday
        month = run_date.month
        season = SeasonCode.from_month(month)

        # Season matches rows where season_code = 'all' OR season_code matches
        # AND the month falls inside [effective_month_start, effective_month_end]
        # (with year-wrap support)
        stmt = (
            select(BaselineScheduleModel)
            .where(
                and_(
                    BaselineScheduleModel.device_id == device_id,
                    BaselineScheduleModel.day_of_week == weekday,
                    BaselineScheduleModel.is_active.is_(True),
                    or_(
                        BaselineScheduleModel.season_code == "all",
                        and_(
                            BaselineScheduleModel.season_code == season.value,
                            # Normal range (no year wrap)
                            or_(
                                and_(
                                    BaselineScheduleModel.effective_month_start <= month,
                                    BaselineScheduleModel.effective_month_end >= month,
                                    BaselineScheduleModel.effective_month_end
                                    >= BaselineScheduleModel.effective_month_start,
                                ),
                                # Year-wrap range (e.g. winter: 12 → 2)
                                and_(
                                    BaselineScheduleModel.effective_month_end
                                    < BaselineScheduleModel.effective_month_start,
                                    or_(
                                        BaselineScheduleModel.effective_month_start <= month,
                                        BaselineScheduleModel.effective_month_end >= month,
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
            )
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_entity(r) for r in rows]

    async def save(self, schedule: BaselineSchedule) -> None:
        model = self._to_model(schedule)
        self._session.add(model)
        await self._session.flush()

    async def deactivate(self, schedule_id: UUID) -> None:
        result = await self._session.get(BaselineScheduleModel, schedule_id)
        if result:
            result.is_active = False
            await self._session.flush()

    # ── Mapping helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _to_entity(m: BaselineScheduleModel) -> BaselineSchedule:
        return BaselineSchedule(
            id=m.id,
            device_id=m.device_id,
            day_of_week=m.day_of_week,
            season_code=SeasonCode(m.season_code),
            effective_month_start=m.effective_month_start,
            effective_month_end=m.effective_month_end,
            start_time=m.start_time,
            duration_minutes=m.duration_minutes,
            is_active=m.is_active,
            grass_type=m.grass_type,
            notes=m.notes,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _to_model(e: BaselineSchedule) -> BaselineScheduleModel:
        return BaselineScheduleModel(
            id=e.id,
            device_id=e.device_id,
            day_of_week=e.day_of_week,
            season_code=e.season_code.value,
            effective_month_start=e.effective_month_start,
            effective_month_end=e.effective_month_end,
            start_time=e.start_time,
            duration_minutes=e.duration_minutes,
            is_active=e.is_active,
            grass_type=e.grass_type,
            notes=e.notes,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
