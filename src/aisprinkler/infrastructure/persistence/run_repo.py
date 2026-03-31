"""SQLAlchemy implementation of RunRepository."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.domain.entities.adjustment_run import AdjustmentRun, RunState, TriggerType
from aisprinkler.domain.repositories.run_repository import RunRepository
from aisprinkler.infrastructure.persistence.models import AdjustmentRunModel


class SqlAlchemyRunRepository(RunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, run: AdjustmentRun) -> AdjustmentRun:
        model = AdjustmentRunModel(
            id=run.id,
            correlation_id=run.correlation_id,
            device_id=run.device_id,
            run_date=run.run_date,
            state=run.state.value,
            trigger_type=run.trigger_type.value,
            confidence_threshold=run.confidence_threshold,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return run

    async def get(self, run_id: UUID) -> AdjustmentRun | None:
        row = await self._session.get(AdjustmentRunModel, run_id)
        return self._to_entity(row) if row else None

    async def get_by_dedupe_key(
        self, device_id: UUID, run_date: date, trigger_type: str
    ) -> AdjustmentRun | None:
        stmt = select(AdjustmentRunModel).where(
            AdjustmentRunModel.device_id == device_id,
            AdjustmentRunModel.run_date == run_date,
            AdjustmentRunModel.trigger_type == trigger_type,
        )
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        return self._to_entity(row) if row else None

    async def update_state(self, run_id: UUID, state: RunState) -> None:
        row = await self._session.get(AdjustmentRunModel, run_id)
        if row:
            row.state = state.value
            await self._session.flush()

    async def list_pending_reviews(self) -> list[AdjustmentRun]:
        stmt = select(AdjustmentRunModel).where(
            AdjustmentRunModel.state == RunState.MANUAL_REVIEW.value
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    @staticmethod
    def _to_entity(m: AdjustmentRunModel) -> AdjustmentRun:
        return AdjustmentRun(
            id=m.id,
            correlation_id=m.correlation_id,
            device_id=m.device_id,
            run_date=m.run_date,
            trigger_type=TriggerType(m.trigger_type),
            confidence_threshold=m.confidence_threshold,
            state=RunState(m.state),
            started_at=m.started_at,
            finished_at=m.finished_at,
            created_at=m.created_at,
        )
