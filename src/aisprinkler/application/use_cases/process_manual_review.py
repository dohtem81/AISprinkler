"""ProcessManualReviewUseCase – approve or reject a queued manual review run."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aisprinkler.application.ports.executor_port import ExecutionCommand, ExecutorPort
from aisprinkler.domain.entities.adjustment_run import RunState
from aisprinkler.domain.repositories.run_repository import RunRepository
from aisprinkler.domain.value_objects.recommendation import RecommendationAction


@dataclass(frozen=True)
class ManualReviewDecision:
    run_id: UUID
    approved: bool
    override_action: RecommendationAction | None = None
    override_duration_minutes: int | None = None
    reviewed_by: str = "operator"
    reason: str = ""


class ProcessManualReviewUseCase:
    def __init__(
        self,
        run_repo: RunRepository,
        executor_port: ExecutorPort,
    ) -> None:
        self._run_repo = run_repo
        self._executor_port = executor_port

    async def execute(self, decision: ManualReviewDecision) -> None:
        run = await self._run_repo.get(decision.run_id)
        if run is None:
            raise ValueError(f"Run {decision.run_id} not found")
        if run.state != RunState.MANUAL_REVIEW:
            raise ValueError(f"Run {decision.run_id} is not in manual_review state")

        if not decision.approved:
            run.fail()
            await self._run_repo.update_state(run.id, RunState.FAILED)
            return

        # Apply operator-provided or existing action
        action = decision.override_action or RecommendationAction.KEEP
        duration = decision.override_duration_minutes

        command = ExecutionCommand(
            run_id=run.id,
            device_id=run.device_id,
            correlation_id=run.correlation_id,
            action=action,
            final_duration_minutes=duration,
            effective_start_time="06:00",  # TODO: load from schedule
        )
        await self._executor_port.dispatch(command)
        run.close()
        await self._run_repo.update_state(run.id, RunState.CLOSED)
