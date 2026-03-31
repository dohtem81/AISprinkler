"""Unit tests for domain entities and value objects."""

from __future__ import annotations

import pytest

from aisprinkler.domain.entities.adjustment_run import AdjustmentRun, RunState, TriggerType
from aisprinkler.domain.entities.baseline_schedule import BaselineSchedule
from aisprinkler.domain.value_objects.recommendation import Recommendation, RecommendationAction
from aisprinkler.domain.value_objects.season import SeasonCode
from aisprinkler.domain.value_objects.weather_context import WeatherContext

import uuid
from datetime import date, time


# ── SeasonCode ────────────────────────────────────────────────────────────────

class TestSeasonCode:
    @pytest.mark.parametrize("month,expected", [
        (3, SeasonCode.SPRING), (4, SeasonCode.SPRING),
        (5, SeasonCode.SUMMER), (7, SeasonCode.SUMMER), (9, SeasonCode.SUMMER),
        (10, SeasonCode.FALL),  (11, SeasonCode.FALL),
        (12, SeasonCode.WINTER), (1, SeasonCode.WINTER), (2, SeasonCode.WINTER),
    ])
    def test_from_month(self, month: int, expected: SeasonCode) -> None:
        assert SeasonCode.from_month(month) == expected


# ── BaselineSchedule ──────────────────────────────────────────────────────────

class TestBaselineSchedule:
    def _make(self, month_start: int, month_end: int) -> BaselineSchedule:
        return BaselineSchedule(
            device_id=uuid.uuid4(),
            day_of_week=0,
            season_code=SeasonCode.SUMMER,
            effective_month_start=month_start,
            effective_month_end=month_end,
            start_time=time(5, 30),
            duration_minutes=25,
        )

    def test_normal_range_covers(self) -> None:
        s = self._make(5, 9)
        assert s.covers_month(5) is True
        assert s.covers_month(7) is True
        assert s.covers_month(9) is True
        assert s.covers_month(4) is False
        assert s.covers_month(10) is False

    def test_year_wrap_detected(self) -> None:
        s = self._make(12, 2)  # winter
        assert s.is_year_wrap() is True
        assert s.covers_month(12) is True
        assert s.covers_month(1) is True
        assert s.covers_month(2) is True
        assert s.covers_month(3) is False

    def test_invalid_day_of_week_raises(self) -> None:
        with pytest.raises(ValueError):
            BaselineSchedule(
                device_id=uuid.uuid4(),
                day_of_week=7,
                season_code=SeasonCode.SUMMER,
                effective_month_start=5,
                effective_month_end=9,
                start_time=time(5, 30),
                duration_minutes=25,
            )

    def test_zero_duration_raises(self) -> None:
        with pytest.raises(ValueError):
            BaselineSchedule(
                device_id=uuid.uuid4(),
                day_of_week=0,
                season_code=SeasonCode.SUMMER,
                effective_month_start=5,
                effective_month_end=9,
                start_time=time(5, 30),
                duration_minutes=0,
            )


# ── AdjustmentRun state machine ───────────────────────────────────────────────

class TestAdjustmentRun:
    def _make_run(self) -> AdjustmentRun:
        return AdjustmentRun(
            device_id=uuid.uuid4(),
            run_date=date.today(),
            trigger_type=TriggerType.DAILY,
            confidence_threshold=0.70,
        )

    def test_initial_state_is_queued(self) -> None:
        run = self._make_run()
        assert run.state == RunState.QUEUED

    def test_valid_transition(self) -> None:
        run = self._make_run()
        run.transition_to(RunState.COLLECTING_DATA)
        assert run.state == RunState.COLLECTING_DATA

    def test_no_transition_from_terminal_state(self) -> None:
        run = self._make_run()
        run.close()
        assert run.state == RunState.CLOSED
        with pytest.raises(ValueError):
            run.transition_to(RunState.COLLECTING_DATA)

    def test_close_sets_finished_at(self) -> None:
        run = self._make_run()
        run.close()
        assert run.finished_at is not None

    def test_fail_sets_terminal_state(self) -> None:
        run = self._make_run()
        run.fail()
        assert run.state == RunState.FAILED
        assert run.state.is_terminal()


# ── Recommendation validation ─────────────────────────────────────────────────

class TestRecommendation:
    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            Recommendation(
                action=RecommendationAction.KEEP,
                recommended_duration_minutes=25,
                confidence_score=1.5,
                rationale="test",
            )

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValueError):
            Recommendation(
                action=RecommendationAction.REDUCE,
                recommended_duration_minutes=-5,
                confidence_score=0.80,
                rationale="test",
            )

    def test_skip_with_none_duration_is_valid(self) -> None:
        r = Recommendation(
            action=RecommendationAction.SKIP,
            recommended_duration_minutes=None,
            confidence_score=0.95,
            rationale="skip test",
        )
        assert r.action == RecommendationAction.SKIP


# ── WeatherContext helpers ────────────────────────────────────────────────────

class TestWeatherContext:
    def test_heavy_rain_flag(self) -> None:
        w = WeatherContext(rain_last_24h_mm=12.0, rain_forecast_next_24h_mm=0.0, rain_probability_pct=20.0)
        assert w.is_heavy_rain_observed() is True
        assert w.is_heavy_rain_observed(threshold_mm=15.0) is False

    def test_high_forecast_flag(self) -> None:
        w = WeatherContext(rain_last_24h_mm=0.0, rain_forecast_next_24h_mm=9.0, rain_probability_pct=20.0)
        assert w.is_high_rain_forecast() is True

    def test_probability_flag(self) -> None:
        w = WeatherContext(rain_last_24h_mm=0.0, rain_forecast_next_24h_mm=0.0, rain_probability_pct=65.0)
        assert w.is_high_rain_probability() is True
