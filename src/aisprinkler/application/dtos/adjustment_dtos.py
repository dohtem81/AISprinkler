"""DTOs for the daily adjustment use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from aisprinkler.domain.entities.adjustment_run import RunState
from aisprinkler.domain.value_objects.recommendation import RecommendationAction


@dataclass(frozen=True)
class DailyAdjustmentRequest:
    device_id: UUID
    run_date: date
    trigger_type: str = "daily"
    as_of: datetime | None = None       # defaults to now() inside use case
    maintenance_blackout: bool = False


@dataclass(frozen=True)
class DailyAdjustmentResult:
    run_id: UUID
    correlation_id: UUID
    final_state: RunState
    final_action: RecommendationAction | None
    final_duration_minutes: int | None
    auto_applied: bool
    manual_review_required: bool
    rules_applied: list[str] = field(default_factory=list)
    confidence_score: float | None = None
    rationale: str | None = None
