"""Schedules router – manage baseline schedules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.domain.entities.baseline_schedule import BaselineKind, BaselineSchedule
from aisprinkler.infrastructure.persistence.db import get_db_session
from aisprinkler.infrastructure.persistence.schedule_repo import SqlAlchemyScheduleRepository

router = APIRouter()


# ── Request / response models ──────────────────────────────────────────────────

class CreateCurrentScheduleRequest(BaseModel):
    device_id: UUID
    schedule_date: date
    start_time: time
    duration_minutes: int = Field(gt=0)
    original_schedule_id: UUID | None = None
    grass_type: str | None = None
    notes: str | None = None
    source: str = "manual"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/")
async def list_schedules(
    device_id: UUID,
    start_date: date | None = None,
    days: int = 7,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    effective_start = start_date or date.today()
    effective_days = max(1, min(days, 14))
    end_date = effective_start + timedelta(days=effective_days - 1)

    repo = SqlAlchemyScheduleRepository(session)
    original = await repo.list_for_range(
        device_id,
        effective_start,
        end_date,
        baseline_kind=BaselineKind.ORIGINAL,
    )
    current = await repo.list_for_range(
        device_id,
        effective_start,
        end_date,
        baseline_kind=BaselineKind.CURRENT,
        include_history=True,
    )

    return {
        "device_id": str(device_id),
        "start_date": effective_start.isoformat(),
        "days": effective_days,
        "original_baseline": [_serialize_schedule(item) for item in original],
        "current_baseline": [_serialize_schedule(item) for item in current],
    }


@router.get("/grafana/current")
async def export_current_schedule_for_grafana(
    device_id: UUID,
    start_date: date | None = None,
    days: int = 7,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    """Export current schedule rows in Grafana-friendly table/timeline format."""
    effective_start = start_date or date.today()
    effective_days = max(1, min(days, 31))
    end_date = effective_start + timedelta(days=effective_days - 1)

    repo = SqlAlchemyScheduleRepository(session)
    current_rows = await repo.list_for_range(
        device_id,
        effective_start,
        end_date,
        baseline_kind=BaselineKind.CURRENT,
        include_history=False,
    )
    return {
        "device_id": str(device_id),
        "start_date": effective_start.isoformat(),
        "days": effective_days,
        "rows": [_serialize_grafana_schedule(item) for item in current_rows],
    }


@router.post("/", status_code=201)
async def create_current_schedule(
    body: CreateCurrentScheduleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    """Persist a new current-baseline entry, superseding any visible row for the
    same (device_id, schedule_date, start_time) slot."""
    schedule = BaselineSchedule(
        id=uuid4(),
        device_id=body.device_id,
        schedule_date=body.schedule_date,
        start_time=body.start_time,
        duration_minutes=body.duration_minutes,
        baseline_kind=BaselineKind.CURRENT,
        original_schedule_id=body.original_schedule_id,
        grass_type=body.grass_type,
        notes=body.notes,
        source=body.source,
    )
    repo = SqlAlchemyScheduleRepository(session)
    await repo.save(schedule)
    await session.commit()
    return _serialize_schedule(schedule)


@router.delete("/{schedule_id}", status_code=200)
async def deactivate_schedule(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    """Soft-delete a schedule entry (sets is_active=False / superseded_at=now).
    Returns 404 when the schedule_id is not found in either table."""
    from aisprinkler.infrastructure.persistence.models import (
        CurrentBaselineScheduleModel,
        OriginalBaselineScheduleModel,
    )

    current = await session.get(CurrentBaselineScheduleModel, schedule_id)
    if current is not None:
        if not current.is_active and current.superseded_at is not None:
            raise HTTPException(status_code=409, detail="Schedule already deactivated")
        repo = SqlAlchemyScheduleRepository(session)
        await repo.deactivate(schedule_id)
        await session.commit()
        return {"deactivated": True, "schedule_id": str(schedule_id)}

    original = await session.get(OriginalBaselineScheduleModel, schedule_id)
    if original is not None:
        repo = SqlAlchemyScheduleRepository(session)
        await repo.deactivate(schedule_id)
        await session.commit()
        return {"deactivated": True, "schedule_id": str(schedule_id)}

    raise HTTPException(status_code=404, detail="Schedule not found")


# ── Serialization ──────────────────────────────────────────────────────────────

def _serialize_schedule(schedule: BaselineSchedule) -> dict[str, object]:
    return {
        "id": str(schedule.id),
        "schedule_date": schedule.schedule_date.isoformat(),
        "start_time": schedule.start_time.isoformat(),
        "duration_minutes": schedule.duration_minutes,
        "baseline_kind": schedule.baseline_kind.value,
        "is_active": schedule.is_active,
        "grass_type": schedule.grass_type,
        "notes": schedule.notes,
        "source": schedule.source,
        "original_schedule_id": (
            str(schedule.original_schedule_id) if schedule.original_schedule_id else None
        ),
        "superseded_at": (
            schedule.superseded_at.isoformat() if schedule.superseded_at else None
        ),
        "created_at": schedule.created_at.isoformat(),
        "updated_at": schedule.updated_at.isoformat(),
    }


def _serialize_grafana_schedule(schedule: BaselineSchedule) -> dict[str, object]:
    schedule_start = datetime.combine(schedule.schedule_date, schedule.start_time)
    schedule_end = schedule_start + timedelta(minutes=schedule.duration_minutes)
    return {
        "schedule_id": str(schedule.id),
        "device_id": str(schedule.device_id),
        "time": schedule_start.isoformat(),
        "time_end": schedule_end.isoformat(),
        "schedule_date": schedule.schedule_date.isoformat(),
        "start_time": schedule.start_time.isoformat(),
        "duration_minutes": schedule.duration_minutes,
        "state": "active" if schedule.is_visible() else "inactive",
        "source": schedule.source,
        "notes": schedule.notes,
    }
