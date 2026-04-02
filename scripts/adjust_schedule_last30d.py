#!/usr/bin/env python
"""Replay daily adjustments for the last N days using persisted weather history.

For each day in the window, this script builds a WeatherContext from
weather_forecast_hour rows marked is_observed=true and runs the normal
RunDailyAdjustmentUseCase flow.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.application.dtos.adjustment_dtos import DailyAdjustmentRequest
from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.application.ports.weather_port import WeatherPort
from aisprinkler.application.use_cases.run_daily_adjustment import RunDailyAdjustmentUseCase
from aisprinkler.domain.services.rule_engine import RuleEngine
from aisprinkler.domain.value_objects.agent_decision_trace import AgentDecisionTrace
from aisprinkler.domain.value_objects.recommendation import Recommendation, RecommendationAction
from aisprinkler.domain.value_objects.weather_context import WeatherContext
from aisprinkler.infrastructure.agent.langchain_agent import LangChainAgentAdapter
from aisprinkler.infrastructure.executor.device_adapter import NoOpDeviceAdapter
from aisprinkler.infrastructure.persistence.bootstrap import bootstrap_database
from aisprinkler.infrastructure.persistence.db import get_session_factory
from aisprinkler.infrastructure.persistence.models import WeatherForecastHourModel, WeatherLocationModel
from aisprinkler.infrastructure.persistence.run_repo import SqlAlchemyRunRepository
from aisprinkler.infrastructure.persistence.schedule_repo import SqlAlchemyScheduleRepository

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class HistoricalWeatherPort(WeatherPort):
    def __init__(self, session: AsyncSession, zipcode: str) -> None:
        self._session = session
        self._zipcode = zipcode

    async def get_weather_context(self, device_id: UUID, as_of: datetime) -> WeatherContext:
        del device_id

        as_of_utc = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        past_start = as_of_utc - timedelta(hours=24)
        future_end = as_of_utc + timedelta(hours=24)

        location_stmt = select(WeatherLocationModel.id).where(WeatherLocationModel.zipcode == self._zipcode)
        location_id = (await self._session.execute(location_stmt)).scalar_one_or_none()
        if location_id is None:
            logger.warning("No weather_location row for zipcode=%s; using dry fallback", self._zipcode)
            return WeatherContext(
                rain_last_24h_mm=0.0,
                rain_forecast_next_24h_mm=0.0,
                rain_probability_pct=0.0,
                temperature_c=None,
                humidity_pct=None,
                wind_speed_kmh=None,
                provider="historical_replay",
                is_fallback_provider=True,
            )

        rows_stmt = (
            select(WeatherForecastHourModel)
            .where(
                and_(
                    WeatherForecastHourModel.location_id == location_id,
                    WeatherForecastHourModel.is_observed.is_(True),
                    WeatherForecastHourModel.forecast_hour >= past_start,
                    WeatherForecastHourModel.forecast_hour <= future_end,
                )
            )
            .order_by(WeatherForecastHourModel.forecast_hour.asc())
        )
        rows = (await self._session.execute(rows_stmt)).scalars().all()
        if not rows:
            logger.warning(
                "No observed weather rows in [%s, %s] for zipcode=%s; using dry fallback",
                past_start,
                future_end,
                self._zipcode,
            )
            return WeatherContext(
                rain_last_24h_mm=0.0,
                rain_forecast_next_24h_mm=0.0,
                rain_probability_pct=0.0,
                temperature_c=None,
                humidity_pct=None,
                wind_speed_kmh=None,
                provider="historical_replay",
                is_fallback_provider=True,
            )

        last_rows = [r for r in rows if r.forecast_hour <= as_of_utc]
        next_rows = [r for r in rows if r.forecast_hour > as_of_utc]

        rain_last_24h_mm = round(sum((r.rain_mm or 0.0) for r in last_rows), 2)
        rain_forecast_next_24h_mm = round(sum((r.rain_mm or 0.0) for r in next_rows), 2)

        inferred_probs: list[float] = []
        for r in next_rows:
            if r.rain_probability_pct is not None:
                inferred_probs.append(float(r.rain_probability_pct))
            elif (r.rain_mm or 0.0) > 0:
                inferred_probs.append(100.0)
            else:
                inferred_probs.append(0.0)
        rain_probability_pct = round(max(inferred_probs, default=0.0), 1)

        nearest = min(rows, key=lambda r: abs((r.forecast_hour - as_of_utc).total_seconds()))
        return WeatherContext(
            rain_last_24h_mm=rain_last_24h_mm,
            rain_forecast_next_24h_mm=rain_forecast_next_24h_mm,
            rain_probability_pct=rain_probability_pct,
            temperature_c=nearest.temperature_c,
            humidity_pct=nearest.humidity_pct,
            wind_speed_kmh=nearest.wind_speed_kmh,
            provider="historical_replay",
            is_fallback_provider=False,
        )


class HeuristicAgentAdapter(AgentPort):
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
        del run_id, correlation_id, device_id
        recommendation = Recommendation(
            action=RecommendationAction.KEEP,
            recommended_duration_minutes=baseline_duration_minutes,
            confidence_score=0.9,
            rationale="Heuristic fallback adapter in replay mode.",
            assumptions=["Heuristic replay mode"],
            policy_version=policy_version,
            prompt_version=prompt_version,
            model_name="heuristic-replay",
            model_version="v1",
            weather_source_provider=weather.provider,
        )
        return AgentDecisionTrace(
            recommendation=recommendation,
            prompt_text="heuristic replay",
            response_text="heuristic replay",
            request_payload={},
            response_payload={
                "recommendation_action": recommendation.action.value,
                "recommended_duration_minutes": recommendation.recommended_duration_minutes,
                "confidence_score": recommendation.confidence_score,
                "rationale": recommendation.rationale,
            },
        )


def _build_agent_adapter() -> AgentPort:
    mode = os.getenv("AGENT_MODE", "heuristic").strip().lower()
    if mode == "langchain":
        return LangChainAgentAdapter()
    return HeuristicAgentAdapter()


async def main() -> None:
    device_id_raw = os.getenv("DEVICE_ID", "00000000-0000-0000-0000-000000000001")
    try:
        device_id = uuid.UUID(device_id_raw)
    except ValueError:
        logger.error("Invalid DEVICE_ID: %s", device_id_raw)
        sys.exit(1)

    days_back = int(os.getenv("ADJUST_HISTORY_DAYS", "30"))
    if days_back <= 0:
        logger.error("ADJUST_HISTORY_DAYS must be > 0")
        sys.exit(1)

    zipcode = os.getenv("WEATHER_ZIPCODE", "36527")
    end_day = date.today()
    start_day = end_day - timedelta(days=days_back - 1)

    logger.info(
        "Replaying adjustments: device=%s start=%s end=%s days=%s zipcode=%s",
        device_id,
        start_day,
        end_day,
        days_back,
        zipcode,
    )

    await bootstrap_database()

    session_factory = get_session_factory()
    async with session_factory() as session:
        use_case = RunDailyAdjustmentUseCase(
            schedule_repo=SqlAlchemyScheduleRepository(session),
            run_repo=SqlAlchemyRunRepository(session),
            weather_port=HistoricalWeatherPort(session, zipcode=zipcode),
            agent_port=_build_agent_adapter(),
            executor_port=NoOpDeviceAdapter(),
            rule_engine=RuleEngine(),
            confidence_threshold=float(os.getenv("CONFIDENCE_AUTO_APPLY_THRESHOLD", "0.70")),
            max_auto_adjustment_pct=float(os.getenv("MAX_AUTO_ADJUSTMENT_PCT", "20")),
            policy_version=os.getenv("POLICY_VERSION", "v1.0.0"),
            prompt_version=os.getenv("PROMPT_VERSION", "prompt.v1.0.0"),
        )

        succeeded = 0
        failed = 0
        day = start_day
        while day <= end_day:
            as_of = datetime.combine(day, time(6, 0), tzinfo=timezone.utc)
            request = DailyAdjustmentRequest(
                device_id=device_id,
                run_date=day,
                trigger_type="manual",
                as_of=as_of,
            )
            try:
                result = await use_case.execute(request)
                await session.commit()
                succeeded += 1
                logger.info(
                    "Adjusted day=%s run_id=%s state=%s action=%s duration=%s",
                    day,
                    result.run_id,
                    result.final_state.value,
                    result.final_action.value if result.final_action else None,
                    result.final_duration_minutes,
                )
            except Exception as exc:
                await session.rollback()
                failed += 1
                logger.exception("Adjustment failed for day=%s: %s", day, exc)
            day += timedelta(days=1)

    logger.info("Replay complete: succeeded=%s failed=%s", succeeded, failed)


if __name__ == "__main__":
    asyncio.run(main())
