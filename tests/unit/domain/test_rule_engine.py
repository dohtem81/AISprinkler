"""Unit tests for the deterministic RuleEngine."""

from __future__ import annotations

import pytest

from aisprinkler.domain.services.rule_engine import RuleEngine
from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)
from aisprinkler.domain.value_objects.weather_context import WeatherContext


@pytest.fixture()
def engine() -> RuleEngine:
    return RuleEngine()


@pytest.fixture()
def dry_weather() -> WeatherContext:
    return WeatherContext(
        rain_last_24h_mm=0.0,
        rain_forecast_next_24h_mm=0.0,
        rain_probability_pct=5.0,
    )


def _recommendation(
    action: RecommendationAction,
    duration: int | None = 25,
    confidence: float = 0.90,
    policy_version: str = "v1.0.0",
) -> Recommendation:
    return Recommendation(
        action=action,
        recommended_duration_minutes=duration,
        confidence_score=confidence,
        rationale="test",
        policy_version=policy_version,
    )


# ── Rule 1: Maintenance blackout ──────────────────────────────────────────────

class TestMaintenanceBlackout:
    def test_forces_skip_regardless_of_recommendation(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.INCREASE, duration=30)
        result = engine.apply(
            rec, baseline_duration_minutes=25, weather=dry_weather, maintenance_blackout=True
        )
        assert result.final_action == RecommendationAction.SKIP
        assert result.final_duration_minutes is None
        assert result.overridden is True

    def test_blackout_rule_recorded_in_effects(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.KEEP)
        result = engine.apply(
            rec, baseline_duration_minutes=25, weather=dry_weather, maintenance_blackout=True
        )
        rule_ids = [e.rule_id for e in result.effects]
        assert "maintenance_blackout" in rule_ids


# ── Rule 2: Policy version mismatch ──────────────────────────────────────────

class TestPolicyMismatch:
    def test_routes_to_manual_review_signal(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.KEEP, policy_version="v0.9.0")
        result = engine.apply(
            rec, baseline_duration_minutes=25, weather=dry_weather, policy_version="v1.0.0"
        )
        rule_ids = [e.rule_id for e in result.effects]
        assert "policy_mismatch_manual_review" in rule_ids
        assert result.overridden is True


# ── Rule 3: Auto-adjustment clamp ────────────────────────────────────────────

class TestAutoAdjustmentClamp:
    def test_clamps_increase_beyond_20pct(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        # Baseline 25 min, +20% max = 30 min; agent proposes 40 min
        rec = _recommendation(RecommendationAction.INCREASE, duration=40)
        result = engine.apply(
            rec,
            baseline_duration_minutes=25,
            weather=dry_weather,
            max_auto_adjustment_pct=20.0,
        )
        assert result.final_duration_minutes == 30
        assert any(e.rule_id == "clamp_auto_adjustment" for e in result.effects)

    def test_clamps_reduce_below_20pct(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        # Baseline 25 min, -20% floor = 20 min; agent proposes 10 min
        rec = _recommendation(RecommendationAction.REDUCE, duration=10)
        result = engine.apply(
            rec,
            baseline_duration_minutes=25,
            weather=dry_weather,
            max_auto_adjustment_pct=20.0,
        )
        assert result.final_duration_minutes == 20

    def test_no_clamp_when_within_bounds(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.REDUCE, duration=22)
        result = engine.apply(
            rec, baseline_duration_minutes=25, weather=dry_weather, max_auto_adjustment_pct=20.0
        )
        assert result.final_duration_minutes == 22
        assert not any(e.rule_id == "clamp_auto_adjustment" for e in result.effects)

    def test_keep_action_not_clamped(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.KEEP, duration=25)
        result = engine.apply(rec, baseline_duration_minutes=25, weather=dry_weather)
        assert result.final_duration_minutes == 25


# ── Rule 4: Device hard limits ────────────────────────────────────────────────

class TestDeviceHardLimits:
    def test_cannot_exceed_device_max(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.INCREASE, duration=35)
        result = engine.apply(
            rec,
            baseline_duration_minutes=25,
            weather=dry_weather,
            max_auto_adjustment_pct=50.0,  # allow increase
            device_max_minutes=30,
        )
        assert result.final_duration_minutes == 30

    def test_cannot_go_below_device_min(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.REDUCE, duration=3)
        result = engine.apply(
            rec,
            baseline_duration_minutes=25,
            weather=dry_weather,
            max_auto_adjustment_pct=100.0,  # allow deep reduce
            device_min_minutes=5,
        )
        assert result.final_duration_minutes == 5


# ── No-op paths ───────────────────────────────────────────────────────────────

class TestNoOpPaths:
    def test_skip_action_passes_through(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.SKIP, duration=None)
        result = engine.apply(rec, baseline_duration_minutes=25, weather=dry_weather)
        assert result.final_action == RecommendationAction.SKIP
        assert result.final_duration_minutes is None

    def test_clean_run_has_no_effects(
        self, engine: RuleEngine, dry_weather: WeatherContext
    ) -> None:
        rec = _recommendation(RecommendationAction.KEEP, duration=25)
        result = engine.apply(rec, baseline_duration_minutes=25, weather=dry_weather)
        assert result.effects == []
        assert result.overridden is False
