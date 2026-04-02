"""Run repository interface (domain port)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from aisprinkler.domain.entities.adjustment_run import AdjustmentRun, RunState
from aisprinkler.domain.value_objects.agent_decision_trace import AgentDecisionTrace


class RunRepository(ABC):
    @abstractmethod
    async def create(self, run: AdjustmentRun) -> AdjustmentRun: ...

    @abstractmethod
    async def get(self, run_id: UUID) -> AdjustmentRun | None: ...

    @abstractmethod
    async def get_by_dedupe_key(
        self, device_id: UUID, run_date: date, trigger_type: str
    ) -> AdjustmentRun | None: ...

    @abstractmethod
    async def update_state(self, run_id: UUID, state: RunState) -> None: ...

    @abstractmethod
    async def list_pending_reviews(self) -> list[AdjustmentRun]: ...

    @abstractmethod
    async def save_agent_trace(
        self,
        run_id: UUID,
        correlation_id: UUID,
        trace: AgentDecisionTrace,
        *,
        prompt_version: str,
        policy_version: str,
    ) -> None: ...
