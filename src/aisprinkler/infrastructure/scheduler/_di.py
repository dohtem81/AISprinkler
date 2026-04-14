"""Dependency wiring for scheduler-triggered use cases."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.application.dtos.adjustment_dtos import (
    DailyAdjustmentRequest,
    DailyAdjustmentResult,
)
from aisprinkler.application.use_cases.run_daily_adjustment import RunDailyAdjustmentUseCase
from aisprinkler.domain.services.rule_engine import RuleEngine
from aisprinkler.domain.value_objects.agent_decision_trace import AgentDecisionTrace
from aisprinkler.domain.value_objects.recommendation import Recommendation, RecommendationAction
from aisprinkler.domain.value_objects.weather_context import WeatherContext
from aisprinkler.infrastructure.executor.device_adapter import NoOpDeviceAdapter
from aisprinkler.infrastructure.agent.langchain_agent import LangChainAgentAdapter
from aisprinkler.infrastructure.logging_config import configure_logging
from aisprinkler.infrastructure.persistence.bootstrap import bootstrap_database
from aisprinkler.infrastructure.persistence.db import get_session_factory
from aisprinkler.infrastructure.persistence.run_repo import SqlAlchemyRunRepository
from aisprinkler.infrastructure.persistence.schedule_repo import SqlAlchemyScheduleRepository
from aisprinkler.infrastructure.persistence.weather_repo import WeatherRepository
from aisprinkler.infrastructure.weather.forecast_refresh import (
    ForecastRefreshPort,
    build_weather_context_from_rows,
)
from aisprinkler.infrastructure.weather.open_meteo_adapter import OpenMeteoAdapter
from aisprinkler.infrastructure.weather.openweather_adapter import OpenWeatherAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeatherProviderSettings:
    lat: float
    lon: float
    zipcode: str
    city: str | None
    state_code: str | None


@dataclass(frozen=True)
class WeatherForecastRefreshResult:
    location_id: UUID
    zipcode: str
    city: str | None
    state_code: str | None
    provider: str
    days: int
    rows_fetched: int
    rows_persisted: int
    fetched_at: datetime


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


class _PersistingForecastWeatherAdapter(WeatherPort):
    """Fetch forecast from configured provider, persist it, then build context."""

    def __init__(
        self,
        session: AsyncSession,
        provider: ForecastRefreshPort,
        settings: WeatherProviderSettings,
    ) -> None:
        self._session = session
        self._provider = provider
        self._settings = settings

    async def get_weather_context(self, device_id: UUID, as_of: datetime) -> WeatherContext:
        rows, _ = await _persist_forecast_rows(
            session=self._session,
            provider=self._provider,
            settings=self._settings,
            days=7,
            device_id=device_id,
        )
        return build_weather_context_from_rows(
            rows,
            as_of,
            provider_name=self._provider.provider_name,
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
    ) -> AgentDecisionTrace:
        recommendation = Recommendation(
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
        request_payload = {
            "run_id": str(run_id),
            "correlation_id": str(correlation_id),
            "device_id": str(device_id),
            "baseline_duration_minutes": baseline_duration_minutes,
            "weather": {
                "provider": weather.provider,
                "rain_last_24h_mm": weather.rain_last_24h_mm,
                "rain_forecast_next_24h_mm": weather.rain_forecast_next_24h_mm,
                "rain_probability_pct": weather.rain_probability_pct,
            },
            "policy_version": policy_version,
            "prompt_version": prompt_version,
        }
        response_payload = {
            "recommendation_action": recommendation.action.value,
            "recommended_duration_minutes": recommendation.recommended_duration_minutes,
            "confidence_score": recommendation.confidence_score,
            "rationale": recommendation.rationale,
        }
        return AgentDecisionTrace(
            recommendation=recommendation,
            prompt_text=(
                "Heuristic scaffold prompt. "
                f"Baseline duration={baseline_duration_minutes}; weather provider={weather.provider}."
            ),
            response_text=str(response_payload),
            request_payload=request_payload,
            response_payload=response_payload,
        )


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


def _build_agent_adapter() -> AgentPort:
    mode = os.getenv("AGENT_MODE", "heuristic").strip().lower()
    if mode == "heuristic":
        return _HeuristicAgentAdapter()
    if mode == "langchain":
        return LangChainAgentAdapter()
    raise ValueError(
        f"Invalid AGENT_MODE '{mode}'. Supported values: heuristic, langchain"
    )


def _build_weather_adapter(session: AsyncSession) -> WeatherPort:
    provider = _build_configured_weather_provider()
    if isinstance(provider, ForecastRefreshPort):
        return _PersistingForecastWeatherAdapter(
            session=session,
            provider=provider,
            settings=_get_weather_provider_settings(),
        )
    return provider


def _get_weather_provider_settings() -> WeatherProviderSettings:
    return WeatherProviderSettings(
        lat=_get_float("WEATHER_LAT", 30.676),
        lon=_get_float("WEATHER_LON", -87.914),
        zipcode=os.getenv("WEATHER_ZIPCODE", "36527"),
        city=os.getenv("WEATHER_CITY", "Spanish Fort"),
        state_code=os.getenv("WEATHER_STATE", "AL"),
    )


def _get_weather_provider_name() -> str:
    return os.getenv("WEATHER_PROVIDER", "open_meteo").strip().lower()


def _build_configured_weather_provider() -> WeatherPort:
    provider = _get_weather_provider_name()
    settings = _get_weather_provider_settings()
    if provider == "synthetic":
        return _SyntheticWeatherAdapter()

    if provider == "open_meteo":
        return OpenMeteoAdapter(lat=settings.lat, lon=settings.lon)

    if provider == "openweather":
        api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "OPENWEATHER_API_KEY is required when WEATHER_PROVIDER=openweather"
            )
        return OpenWeatherAdapter(api_key=api_key, lat=settings.lat, lon=settings.lon)

    raise ValueError(
        "Invalid WEATHER_PROVIDER "
        f"'{provider}'. Supported values: open_meteo, openweather, synthetic"
    )


def _build_refreshable_weather_provider() -> tuple[ForecastRefreshPort, WeatherProviderSettings]:
    provider = _build_configured_weather_provider()
    if isinstance(provider, ForecastRefreshPort):
        return provider, _get_weather_provider_settings()

    raise ValueError(
        "Configured WEATHER_PROVIDER "
        f"'{_get_weather_provider_name()}' does not support forecast refresh"
    )


async def _persist_forecast_rows(
    session: AsyncSession,
    *,
    provider: ForecastRefreshPort,
    settings: WeatherProviderSettings,
    days: int,
    device_id: UUID | None,
) -> tuple[list[dict[str, Any]], WeatherForecastRefreshResult]:
    fetched_at = datetime.now(timezone.utc)
    rows = await provider.fetch_forecast_hours(days=days)
    weather_repo = WeatherRepository(session)
    location_id = await weather_repo.get_or_create_location(
        zipcode=settings.zipcode,
        lat=settings.lat,
        lon=settings.lon,
        city=settings.city,
        state_code=settings.state_code,
    )
    persisted = await weather_repo.upsert_hourly_rows(location_id, rows)
    logger.info(
        "Persisted forecast rows",
        extra={
            "action": "weather_pull",
            "component": "weather",
            "location": os.getenv("WEATHER_LOCATION_LABEL", "spanish_fort_al"),
            "weather_provider": provider.provider_name,
            "device_id": str(device_id) if device_id is not None else None,
            "rows_fetched": len(rows),
            "rows_persisted": persisted,
            "status": "success",
        },
    )
    return rows, WeatherForecastRefreshResult(
        location_id=location_id,
        zipcode=settings.zipcode,
        city=settings.city,
        state_code=settings.state_code,
        provider=provider.provider_name,
        days=days,
        rows_fetched=len(rows),
        rows_persisted=persisted,
        fetched_at=fetched_at,
    )


async def refresh_weather_forecast(
    session: AsyncSession,
    *,
    days: int = 7,
    device_id: UUID | None = None,
) -> WeatherForecastRefreshResult:
    provider, settings = _build_refreshable_weather_provider()
    _, result = await _persist_forecast_rows(
        session=session,
        provider=provider,
        settings=settings,
        days=days,
        device_id=device_id,
    )
    return result


def build_use_case(session: AsyncSession) -> RunDailyAdjustmentUseCase:
    _ = _get_int("WEATHER_FORECAST_STALENESS_MINUTES", 90)
    return RunDailyAdjustmentUseCase(
        schedule_repo=SqlAlchemyScheduleRepository(session),
        run_repo=SqlAlchemyRunRepository(session),
        weather_port=_build_weather_adapter(session),
        agent_port=_build_agent_adapter(),
        executor_port=NoOpDeviceAdapter(),
        rule_engine=RuleEngine(),
        confidence_threshold=_get_float("CONFIDENCE_AUTO_APPLY_THRESHOLD", 0.70),
        max_auto_adjustment_pct=_get_float("MAX_AUTO_ADJUSTMENT_PCT", 20.0),
        policy_version=os.getenv("POLICY_VERSION", "v1.0.0"),
        prompt_version=os.getenv("PROMPT_VERSION", "prompt.v1.0.0"),
    )


async def execute_daily_adjustment(
    request: DailyAdjustmentRequest,
) -> DailyAdjustmentResult:
    configure_logging()
    await bootstrap_database()
    session_factory = get_session_factory()
    async with session_factory() as session:
        use_case = build_use_case(session)
        result = await use_case.execute(request)
        await session.commit()
        return result
