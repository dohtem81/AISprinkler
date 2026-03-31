"""Root test fixtures shared across all test layers."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from unittest.mock import AsyncMock

import pytest

from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.application.ports.executor_port import (
    ExecutionReceipt,
    ExecutorPort,
)
from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.domain.entities.adjustment_run import AdjustmentRun, RunState, TriggerType
from aisprinkler.domain.entities.baseline_schedule import BaselineSchedule
from aisprinkler.domain.repositories.run_repository import RunRepository
from aisprinkler.domain.repositories.schedule_repository import ScheduleRepository
from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)
from aisprinkler.domain.value_objects.season import SeasonCode
from aisprinkler.domain.value_objects.weather_context import WeatherContext

# ── Shared IDs ────────────────────────────────────────────────────────────────

DEVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
RUN_DATE = date(2026, 7, 15)  # Tuesday, July → summer


# ── Domain fixtures ───────────────────────────────────────────────────────────

@pytest.fixture()
def device_id() -> uuid.UUID:
    return DEVICE_ID


@pytest.fixture()
def run_date() -> date:
    return RUN_DATE


@pytest.fixture()
def summer_schedule() -> BaselineSchedule:
    return BaselineSchedule(
        device_id=DEVICE_ID,
        day_of_week=1,          # Tuesday
        season_code=SeasonCode.SUMMER,
        effective_month_start=5,
        effective_month_end=9,
        start_time=time(5, 30),
        duration_minutes=25,
        grass_type="bermuda",
    )


@pytest.fixture()
def dry_weather() -> WeatherContext:
    """No rain observed or forecast."""
    return WeatherContext(
        rain_last_24h_mm=0.5,
        rain_forecast_next_24h_mm=1.0,
        rain_probability_pct=10.0,
        temperature_c=34.0,
        provider="openweathermap",
    )


@pytest.fixture()
def rainy_weather() -> WeatherContext:
    """Heavy rain observed AND heavy rain forecast."""
    return WeatherContext(
        rain_last_24h_mm=22.0,
        rain_forecast_next_24h_mm=15.0,
        rain_probability_pct=80.0,
        temperature_c=22.0,
        provider="openweathermap",
    )


@pytest.fixture()
def high_confidence_keep_recommendation() -> Recommendation:
    return Recommendation(
        action=RecommendationAction.KEEP,
        recommended_duration_minutes=25,
        confidence_score=0.90,
        rationale="Low rain observed and forecast; maintain baseline.",
        policy_version="v1.0.0",
        prompt_version="prompt.v1.0.0",
    )


@pytest.fixture()
def high_confidence_skip_recommendation() -> Recommendation:
    return Recommendation(
        action=RecommendationAction.SKIP,
        recommended_duration_minutes=None,
        confidence_score=0.95,
        rationale="Heavy rain observed and high probability forecast.",
        policy_version="v1.0.0",
        prompt_version="prompt.v1.0.0",
    )


@pytest.fixture()
def low_confidence_recommendation() -> Recommendation:
    return Recommendation(
        action=RecommendationAction.REDUCE,
        recommended_duration_minutes=20,
        confidence_score=0.50,
        rationale="Mixed signals; low confidence.",
        policy_version="v1.0.0",
        prompt_version="prompt.v1.0.0",
    )


# ── Port mocks ────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_weather_port(dry_weather: WeatherContext) -> WeatherPort:
    port = AsyncMock(spec=WeatherPort)
    port.get_weather_context.return_value = dry_weather
    return port


@pytest.fixture()
def mock_agent_port(high_confidence_keep_recommendation: Recommendation) -> AgentPort:
    port = AsyncMock(spec=AgentPort)
    port.recommend.return_value = high_confidence_keep_recommendation
    return port


@pytest.fixture()
def mock_executor_port() -> ExecutorPort:
    port = AsyncMock(spec=ExecutorPort)
    port.dispatch.return_value = ExecutionReceipt(
        adapter_execution_id=str(uuid.uuid4()),
        accepted=True,
        status="success",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        proof={"noop": True},
    )
    return port


@pytest.fixture()
def mock_schedule_repo(summer_schedule: BaselineSchedule) -> ScheduleRepository:
    repo = AsyncMock(spec=ScheduleRepository)
    repo.get_active_for_date.return_value = [summer_schedule]
    return repo


@pytest.fixture()
def mock_run_repo() -> RunRepository:
    repo = AsyncMock(spec=RunRepository)

    async def create_side_effect(run: AdjustmentRun) -> AdjustmentRun:
        return run

    repo.create.side_effect = create_side_effect
    repo.update_state.return_value = None
    return repo
