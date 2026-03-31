"""BaselineSchedule entity – one row of the pre-configured daily watering plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from uuid import UUID, uuid4

from aisprinkler.domain.value_objects.season import SeasonCode


@dataclass
class BaselineSchedule:
    """One active time-slot in the daily preset schedule.

    day_of_week: 0=Monday … 6=Sunday (matches Python datetime.weekday()).
    """

    device_id: UUID
    day_of_week: int  # 0–6
    season_code: SeasonCode
    effective_month_start: int  # 1–12
    effective_month_end: int    # 1–12
    start_time: time
    duration_minutes: int
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    grass_type: str | None = None
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not (0 <= self.day_of_week <= 6):
            raise ValueError(f"day_of_week must be 0–6, got {self.day_of_week}")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

    def is_year_wrap(self) -> bool:
        """True when the season spans the year boundary (e.g. winter: Dec→Feb)."""
        return self.effective_month_end < self.effective_month_start

    def covers_month(self, month: int) -> bool:
        """Return True if the given calendar month falls inside this schedule's range."""
        if self.is_year_wrap():
            return month >= self.effective_month_start or month <= self.effective_month_end
        return self.effective_month_start <= month <= self.effective_month_end
