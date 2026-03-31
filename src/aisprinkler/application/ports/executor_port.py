"""ExecutorPort – interface that device execution adapters must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aisprinkler.domain.value_objects.recommendation import RecommendationAction


@dataclass(frozen=True)
class ExecutionCommand:
    run_id: UUID
    device_id: UUID
    correlation_id: UUID
    action: RecommendationAction
    final_duration_minutes: int | None  # None for skip
    effective_start_time: str           # "HH:MM" local time


@dataclass(frozen=True)
class ExecutionReceipt:
    adapter_execution_id: str
    accepted: bool
    status: str                         # success | partial | failed | timeout
    started_at: datetime
    completed_at: datetime | None
    proof: dict[str, object]
    error: str | None = None


class ExecutorPort(ABC):
    @abstractmethod
    async def dispatch(self, command: ExecutionCommand) -> ExecutionReceipt:
        """Send the irrigation command to the device and return an execution receipt."""
        ...
