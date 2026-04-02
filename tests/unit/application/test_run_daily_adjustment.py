"""Unit tests for RunDailyAdjustmentUseCase.

All external dependencies (ports + repos) are mocked.
No database, no HTTP calls, no LLM – pure logic testing.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest

from aisprinkler.application.dtos.adjustment_dtos import DailyAdjustmentRequest
from aisprinkler.application.use_cases.run_daily_adjustment import RunDailyAdjustmentUseCase
from aisprinkler.domain.entities.adjustment_run import RunState
from aisprinkler.domain.value_objects.agent_decision_trace import AgentDecisionTrace
from aisprinkler.domain.services.rule_engine import RuleEngine
from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)


def _build_use_case(
    schedule_repo: object,
    run_repo: object,
    weather_port: object,
    agent_port: object,
    executor_port: object,
) -> RunDailyAdjustmentUseCase:
    return RunDailyAdjustmentUseCase(
        schedule_repo=schedule_repo,  # type: ignore[arg-type]
        run_repo=run_repo,             # type: ignore[arg-type]
        weather_port=weather_port,     # type: ignore[arg-type]
        agent_port=agent_port,         # type: ignore[arg-type]
        executor_port=executor_port,   # type: ignore[arg-type]
        rule_engine=RuleEngine(),
        confidence_threshold=0.70,
        max_auto_adjustment_pct=20.0,
        policy_version="v1.0.0",
    )


class TestAutoApplyPath:
    async def test_high_confidence_closes_run(
        self,
        mock_schedule_repo: object,
        mock_run_repo: object,
        mock_weather_port: object,
        mock_agent_port: object,
        mock_executor_port: object,
        device_id: uuid.UUID,
        run_date: date,
    ) -> None:
        uc = _build_use_case(
            mock_schedule_repo, mock_run_repo, mock_weather_port,
            mock_agent_port, mock_executor_port
        )
        request = DailyAdjustmentRequest(device_id=device_id, run_date=run_date)
        result = await uc.execute(request)

        assert result.final_state == RunState.CLOSED
        assert result.auto_applied is True
        assert result.manual_review_required is False
        mock_schedule_repo.save.assert_called_once()  # type: ignore[attr-defined]
        mock_schedule_repo.deactivate.assert_not_called()  # type: ignore[attr-defined]
        mock_run_repo.save_agent_trace.assert_called_once()  # type: ignore[attr-defined]

    async def test_dispatcher_called_once_on_auto_apply(
        self,
        mock_schedule_repo: object,
        mock_run_repo: object,
        mock_weather_port: object,
        mock_agent_port: object,
        mock_executor_port: object,
        device_id: uuid.UUID,
        run_date: date,
    ) -> None:
        uc = _build_use_case(
            mock_schedule_repo, mock_run_repo, mock_weather_port,
            mock_agent_port, mock_executor_port
        )
        await uc.execute(DailyAdjustmentRequest(device_id=device_id, run_date=run_date))
        mock_executor_port.dispatch.assert_called_once()  # type: ignore[attr-defined]


class TestManualReviewPath:
    async def test_low_confidence_routes_to_manual_review(
        self,
        mock_schedule_repo: object,
        mock_run_repo: object,
        mock_weather_port: object,
        low_confidence_recommendation: Recommendation,
        mock_executor_port: object,
        device_id: uuid.UUID,
        run_date: date,
    ) -> None:
        agent_port = AsyncMock()
        agent_port.recommend.return_value = AgentDecisionTrace(
            recommendation=low_confidence_recommendation,
            prompt_text="low-confidence prompt",
            response_text="low-confidence response",
        )

        uc = _build_use_case(
            mock_schedule_repo, mock_run_repo, mock_weather_port,
            agent_port, mock_executor_port
        )
        result = await uc.execute(DailyAdjustmentRequest(device_id=device_id, run_date=run_date))

        assert result.final_state == RunState.MANUAL_REVIEW
        assert result.manual_review_required is True
        assert result.auto_applied is False
        mock_executor_port.dispatch.assert_not_called()  # type: ignore[attr-defined]
        mock_schedule_repo.save.assert_not_called()  # type: ignore[attr-defined]
        mock_schedule_repo.deactivate.assert_not_called()  # type: ignore[attr-defined]

    async def test_maintenance_blackout_routes_to_auto_apply_skip(
        self,
        mock_schedule_repo: object,
        mock_run_repo: object,
        mock_weather_port: object,
        high_confidence_keep_recommendation: Recommendation,
        mock_executor_port: object,
        device_id: uuid.UUID,
        run_date: date,
    ) -> None:
        """Maintenance blackout forces skip action but still auto-applies (rule overrides)."""
        agent_port = AsyncMock()
        agent_port.recommend.return_value = AgentDecisionTrace(
            recommendation=high_confidence_keep_recommendation,
            prompt_text="keep prompt",
            response_text="keep response",
        )

        uc = _build_use_case(
            mock_schedule_repo, mock_run_repo, mock_weather_port,
            agent_port, mock_executor_port
        )
        result = await uc.execute(
            DailyAdjustmentRequest(
                device_id=device_id, run_date=run_date, maintenance_blackout=True
            )
        )

        assert result.final_action == RecommendationAction.SKIP
        assert result.auto_applied is True
        assert "maintenance_blackout" in result.rules_applied
        mock_schedule_repo.save.assert_not_called()  # type: ignore[attr-defined]
        mock_schedule_repo.deactivate.assert_called_once()  # type: ignore[attr-defined]


class TestFailurePath:
    async def test_run_marked_failed_on_exception(
        self,
        mock_schedule_repo: object,
        mock_run_repo: object,
        mock_executor_port: object,
        device_id: uuid.UUID,
        run_date: date,
    ) -> None:
        weather_port = AsyncMock()
        weather_port.get_weather_context.side_effect = RuntimeError("API unavailable")

        agent_port = AsyncMock()

        uc = _build_use_case(
            mock_schedule_repo, mock_run_repo, weather_port,
            agent_port, mock_executor_port
        )
        with pytest.raises(RuntimeError, match="API unavailable"):
            await uc.execute(DailyAdjustmentRequest(device_id=device_id, run_date=run_date))

        # The run repository must have been told to set state to FAILED
        state_calls = [
            call.args[1]
            for call in mock_run_repo.update_state.call_args_list  # type: ignore[attr-defined]
        ]
        assert RunState.FAILED in state_calls
