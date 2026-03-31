"""RunDailyAdjustmentUseCase – orchestrates one complete adjustment run.

Clean Architecture:
  - Depends only on domain entities/VOs and application ports.
  - No import of infrastructure, FastAPI, SQLAlchemy, LangChain, etc.
  - All external collaborators injected via constructor.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from aisprinkler.application.dtos.adjustment_dtos import (
    DailyAdjustmentRequest,
    DailyAdjustmentResult,
)
from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.application.ports.executor_port import ExecutionCommand, ExecutorPort
from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.domain.entities.adjustment_run import AdjustmentRun, RunState, TriggerType
from aisprinkler.domain.repositories.run_repository import RunRepository
from aisprinkler.domain.repositories.schedule_repository import ScheduleRepository
from aisprinkler.domain.services.rule_engine import RuleEngine
from aisprinkler.domain.value_objects.recommendation import RecommendationAction

logger = logging.getLogger(__name__)


class RunDailyAdjustmentUseCase:
    """Executes a single daily irrigation adjustment run end-to-end."""

    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        run_repo: RunRepository,
        weather_port: WeatherPort,
        agent_port: AgentPort,
        executor_port: ExecutorPort,
        rule_engine: RuleEngine,
        *,
        confidence_threshold: float = 0.70,
        max_auto_adjustment_pct: float = 20.0,
        policy_version: str = "v1.0.0",
        prompt_version: str = "prompt.v1.0.0",
    ) -> None:
        self._schedule_repo = schedule_repo
        self._run_repo = run_repo
        self._weather_port = weather_port
        self._agent_port = agent_port
        self._executor_port = executor_port
        self._rule_engine = rule_engine
        self._confidence_threshold = confidence_threshold
        self._max_auto_adjustment_pct = max_auto_adjustment_pct
        self._policy_version = policy_version
        self._prompt_version = prompt_version

    async def execute(self, request: DailyAdjustmentRequest) -> DailyAdjustmentResult:
        as_of = request.as_of or datetime.now(timezone.utc)

        # ── 1. Create and persist the run ─────────────────────────────────────
        run = AdjustmentRun(
            device_id=request.device_id,
            run_date=request.run_date,
            trigger_type=TriggerType(request.trigger_type),
            confidence_threshold=self._confidence_threshold,
        )
        run = await self._run_repo.create(run)
        try:
            # ── 2. Collect data ───────────────────────────────────────────────
            run.transition_to(RunState.COLLECTING_DATA)
            await self._run_repo.update_state(run.id, RunState.COLLECTING_DATA)

            schedules = await self._schedule_repo.get_active_for_date(
                request.device_id, request.run_date
            )
            if not schedules:
                logger.warning("No active baseline schedule found; using safe default 0 min.")
            baseline_duration = schedules[0].duration_minutes if schedules else 0

            weather = await self._weather_port.get_weather_context(request.device_id, as_of)

            # ── 3. Agent reasoning ────────────────────────────────────────────
            run.transition_to(RunState.REASONING)
            await self._run_repo.update_state(run.id, RunState.REASONING)

            recommendation = await self._agent_port.recommend(
                run_id=run.id,
                correlation_id=run.correlation_id,
                device_id=request.device_id,
                baseline_duration_minutes=baseline_duration,
                weather=weather,
                policy_version=self._policy_version,
                prompt_version=self._prompt_version,
            )

            # ── 4. Deterministic rule check ───────────────────────────────────
            run.transition_to(RunState.RULE_CHECK)
            await self._run_repo.update_state(run.id, RunState.RULE_CHECK)

            rule_result = self._rule_engine.apply(
                recommendation=recommendation,
                baseline_duration_minutes=baseline_duration,
                weather=weather,
                maintenance_blackout=request.maintenance_blackout,
                policy_version=self._policy_version,
                max_auto_adjustment_pct=self._max_auto_adjustment_pct,
            )
            rules_applied = [e.rule_id for e in rule_result.effects if e.matched]

            # ── 5. Confidence gate ────────────────────────────────────────────
            run.transition_to(RunState.APPROVAL_GATE)
            await self._run_repo.update_state(run.id, RunState.APPROVAL_GATE)

            # Policy mismatch rule forces manual review regardless of confidence
            policy_mismatch = any(
                e.rule_id == "policy_mismatch_manual_review" for e in rule_result.effects
            )
            below_threshold = recommendation.confidence_score < self._confidence_threshold

            if policy_mismatch or below_threshold:
                run.send_to_manual_review()
                await self._run_repo.update_state(run.id, RunState.MANUAL_REVIEW)
                return DailyAdjustmentResult(
                    run_id=run.id,
                    correlation_id=run.correlation_id,
                    final_state=RunState.MANUAL_REVIEW,
                    final_action=rule_result.final_action,
                    final_duration_minutes=rule_result.final_duration_minutes,
                    auto_applied=False,
                    manual_review_required=True,
                    rules_applied=rules_applied,
                    confidence_score=recommendation.confidence_score,
                    rationale=recommendation.rationale,
                )

            # ── 6. Auto-apply dispatch ────────────────────────────────────────
            run.transition_to(RunState.DISPATCHING)
            await self._run_repo.update_state(run.id, RunState.DISPATCHING)

            start_time = schedules[0].start_time.strftime("%H:%M") if schedules else "06:00"
            command = ExecutionCommand(
                run_id=run.id,
                device_id=request.device_id,
                correlation_id=run.correlation_id,
                action=rule_result.final_action,
                final_duration_minutes=rule_result.final_duration_minutes,
                effective_start_time=start_time,
            )
            _receipt = await self._executor_port.dispatch(command)

            # ── 7. Close run ──────────────────────────────────────────────────
            run.transition_to(RunState.VERIFYING)
            await self._run_repo.update_state(run.id, RunState.VERIFYING)
            run.close()
            await self._run_repo.update_state(run.id, RunState.CLOSED)

            return DailyAdjustmentResult(
                run_id=run.id,
                correlation_id=run.correlation_id,
                final_state=RunState.CLOSED,
                final_action=rule_result.final_action,
                final_duration_minutes=rule_result.final_duration_minutes,
                auto_applied=True,
                manual_review_required=False,
                rules_applied=rules_applied,
                confidence_score=recommendation.confidence_score,
                rationale=recommendation.rationale,
            )

        except Exception:
            run.fail()
            await self._run_repo.update_state(run.id, RunState.FAILED)
            raise
