"""BaselineSchedule entity for a concrete schedule date."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from enum import Enum
from uuid import UUID, uuid4


class BaselineKind(str, Enum):
    ORIGINAL = "original"
    CURRENT = "current"


@dataclass
class BaselineSchedule:
    """One time-slot in a dated baseline schedule window."""

    device_id: UUID
    schedule_date: date
    start_time: time
    duration_minutes: int
    baseline_kind: BaselineKind
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    grass_type: str | None = None
    notes: str | None = None
    source: str = "seed"
    original_schedule_id: UUID | None = None
    superseded_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

    def is_visible(self) -> bool:
        return self.is_active and self.superseded_at is None
