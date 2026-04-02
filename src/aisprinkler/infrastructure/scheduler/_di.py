"""Dependency wiring for scheduler-triggered use cases.

This module intentionally provides a safe default wiring for the current
scaffold state: deterministic in-memory repositories, synthetic weather, and
no-op device execution. It allows worker tasks to run without failing on
missing infrastructure pieces.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from uuid import UUID

from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.application.use_cases.run_daily_adjustment import RunDailyAdjustmentUseCase
from aisprinkler.domain.entities.adjustment_run import AdjustmentRun, RunState
from aisprinkler.domain.entities.baseline_schedule import BaselineSchedule
from aisprinkler.domain.repositories.run_repository import RunRepository
from aisprinkler.domain.repositories.schedule_repository import ScheduleRepository
from aisprinkler.domain.services.rule_engine import RuleEngine
from aisprinkler.domain.value_objects.recommendation import Recommendation, RecommendationAction
from aisprinkler.domain.value_objects.weather_context import WeatherContext
from aisprinkler.infrastructure.executor.device_adapter import NoOpDeviceAdapter


class _InMemoryRunRepository(RunRepository):
    def __init__(self) -> None:
        self._runs: dict[UUID, AdjustmentRun] = {}

    async def create(self, run: AdjustmentRun) -> AdjustmentRun:
        self._runs[run.id] = run
        return run

    async def get(self, run_id: UUID) -> AdjustmentRun | None:
        return self._runs.get(run_id)

    async def get_by_dedupe_key(
        self, device_id: UUID, run_date: date, trigger_type: str
    ) -> AdjustmentRun | None:
        for run in self._runs.values():
            if (
                run.device_id == device_id
                and run.run_date == run_date
                and run.trigger_type.value == trigger_type
            ):
                return run
        return None

    async def update_state(self, run_id: UUID, state: RunState) -> None:
        run = self._runs.get(run_id)
        if run is not None:
            run.state = state

    async def list_pending_reviews(self) -> list[AdjustmentRun]:
        return [r for r in self._runs.values() if r.state == RunState.MANUAL_REVIEW]


class _InMemoryScheduleRepository(ScheduleRepository):
    async def get_active_for_date(
        self, device_id: UUID, run_date: date
    ) -> list[BaselineSchedule]:
        # Scaffold mode: no baseline persistence yet.
        return []

    async def save(self, schedule: BaselineSchedule) -> None:
        return None

    async def deactivate(self, schedule_id: UUID) -> None:
        return None


class _SyntheticWeatherAdapter(WeatherPort):
    async def get_weather_context(self, device_id: UUID, as_of: datetime) -> WeatherContext:
        return WeatherContext(
            rain_last_24h_mm=0.0,
            rain_forecast_next_24h_mm=0.0,
            rain_probability_pct=0.0,
            temperature_c=24.0,
            humidity_pct=55.0,
            wind_speed_kmh=6.0,
            provider="synthetic",
            is_fallback_provider=False,
        )


class _HeuristicAgentAdapter(AgentPort):
    async def recommend(
        self,
        run_id: UUID,
        correlation_id: UUID,
        device_id: UUID,
        baseline_duration_minutes: int,
        weather: WeatherContext,
        policy_version: str,
        prompt_version: str,
    ) -> Recommendation:
        return Recommendation(
            action=RecommendationAction.KEEP,
            recommended_duration_minutes=baseline_duration_minutes,
            confidence_score=0.95,
            rationale="Scaffold heuristic: keep baseline until live LLM adapter is enabled.",
            assumptions=["Synthetic weather context used in scaffold mode."],
            policy_version=policy_version,
            prompt_version=prompt_version,
            model_name="heuristic-scaffold",
            model_version="v0",
            weather_source_provider=weather.provider,
        )


_RUN_REPO = _InMemoryRunRepository()
_SCHEDULE_REPO = _InMemoryScheduleRepository()


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def build_use_case() -> RunDailyAdjustmentUseCase:
    """Build scheduler use case with scaffold-safe defaults.

    This path is intentionally no-op friendly for concept validation.
    """
    _ = _get_int("WEATHER_FORECAST_STALENESS_MINUTES", 90)
    return RunDailyAdjustmentUseCase(
        schedule_repo=_SCHEDULE_REPO,
        run_repo=_RUN_REPO,
        weather_port=_SyntheticWeatherAdapter(),
        agent_port=_HeuristicAgentAdapter(),
        executor_port=NoOpDeviceAdapter(),
        rule_engine=RuleEngine(),
        confidence_threshold=_get_float("CONFIDENCE_AUTO_APPLY_THRESHOLD", 0.70),
        max_auto_adjustment_pct=_get_float("MAX_AUTO_ADJUSTMENT_PCT", 20.0),
        policy_version=os.getenv("POLICY_VERSION", "v1.0.0"),
        prompt_version=os.getenv("PROMPT_VERSION", "prompt.v1.0.0"),
    )