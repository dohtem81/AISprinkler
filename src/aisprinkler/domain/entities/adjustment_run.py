"""AdjustmentRun entity – one end-to-end execution lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class RunState(str, Enum):
    QUEUED = "queued"
    COLLECTING_DATA = "collecting_data"
    REASONING = "reasoning"
    RULE_CHECK = "rule_check"
    APPROVAL_GATE = "approval_gate"
    DISPATCHING = "dispatching"
    VERIFYING = "verifying"
    CLOSED = "closed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"

    def is_terminal(self) -> bool:
        return self.value in ("closed", "failed", "manual_review")


class TriggerType(str, Enum):
    DAILY = "daily"
    EVENT = "event"
    MANUAL = "manual"
    RETRY = "retry"


@dataclass
class AdjustmentRun:
    device_id: UUID
    run_date: date
    trigger_type: TriggerType
    confidence_threshold: float
    id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    state: RunState = RunState.QUEUED
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def transition_to(self, new_state: RunState) -> None:
        if self.state.is_terminal():
            raise ValueError(
                f"Cannot transition from terminal state {self.state!r} to {new_state!r}"
            )
        self.state = new_state

    def close(self) -> None:
        self.transition_to(RunState.CLOSED)
        self.finished_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        self.state = RunState.FAILED
        self.finished_at = datetime.now(timezone.utc)

    def send_to_manual_review(self) -> None:
        self.transition_to(RunState.MANUAL_REVIEW)
        self.finished_at = datetime.now(timezone.utc)
