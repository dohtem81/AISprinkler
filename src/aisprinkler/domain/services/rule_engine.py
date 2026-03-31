"""Deterministic Rule Engine – applies hard policy constraints to an agent recommendation.

This is the normative enforcement layer.  It runs AFTER the AI agent produces its suggestion
and BEFORE the confidence gate decides whether to auto-apply.

Rule definitions cross-reference docs/PROMPTS_AND_RULES.md §4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)
from aisprinkler.domain.value_objects.weather_context import WeatherContext


@dataclass(frozen=True)
class RuleEffect:
    rule_id: str
    matched: bool
    original_action: RecommendationAction
    final_action: RecommendationAction
    original_duration: int | None
    final_duration: int | None
    detail: str


@dataclass
class RuleEngineResult:
    final_action: RecommendationAction
    final_duration_minutes: int | None
    effects: list[RuleEffect] = field(default_factory=list)
    overridden: bool = False


class RuleEngine:
    """Pure-function rule engine.  No I/O – deterministic and fully unit-testable."""

    def apply(
        self,
        recommendation: Recommendation,
        baseline_duration_minutes: int,
        weather: WeatherContext,
        *,
        maintenance_blackout: bool = False,
        device_min_minutes: int = 0,
        device_max_minutes: int = 60,
        policy_version: str = "v1.0.0",
        max_auto_adjustment_pct: float = 20.0,
    ) -> RuleEngineResult:
        effects: list[RuleEffect] = []
        action = recommendation.action
        duration = recommendation.recommended_duration_minutes

        # ── Rule 1: maintenance blackout ─────────────────────────────────────
        if maintenance_blackout:
            eff = RuleEffect(
                rule_id="maintenance_blackout",
                matched=True,
                original_action=action,
                final_action=RecommendationAction.SKIP,
                original_duration=duration,
                final_duration=None,
                detail="Maintenance blackout active – forcing skip.",
            )
            effects.append(eff)
            return RuleEngineResult(
                final_action=RecommendationAction.SKIP,
                final_duration_minutes=None,
                effects=effects,
                overridden=True,
            )

        # ── Rule 2: policy version mismatch ──────────────────────────────────
        if recommendation.policy_version != policy_version:
            eff = RuleEffect(
                rule_id="policy_mismatch_manual_review",
                matched=True,
                original_action=action,
                final_action=action,
                original_duration=duration,
                final_duration=duration,
                detail=f"Policy mismatch: got {recommendation.policy_version!r}, "
                       f"expected {policy_version!r}. Routing to manual review.",
            )
            effects.append(eff)
            # Caller is responsible for routing to manual_review when effect is matched
            return RuleEngineResult(
                final_action=action,
                final_duration_minutes=duration,
                effects=effects,
                overridden=True,
            )

        # ── Rule 3: stale weather context (caller signals via special action) ─
        # Handled upstream; if weather.is_fallback_provider apply no penalty here.

        # ── Rule 4: clamp auto-adjustment to ±max_auto_adjustment_pct ────────
        if action in (RecommendationAction.REDUCE, RecommendationAction.INCREASE) and duration is not None:
            max_delta = baseline_duration_minutes * (max_auto_adjustment_pct / 100.0)
            min_allowed = max(device_min_minutes, round(baseline_duration_minutes - max_delta))
            max_allowed = min(device_max_minutes, round(baseline_duration_minutes + max_delta))
            clamped = max(min_allowed, min(duration, max_allowed))
            if clamped != duration:
                eff = RuleEffect(
                    rule_id="clamp_auto_adjustment",
                    matched=True,
                    original_action=action,
                    final_action=action,
                    original_duration=duration,
                    final_duration=clamped,
                    detail=(
                        f"Duration {duration} clamped to {clamped} "
                        f"(±{max_auto_adjustment_pct}% of baseline {baseline_duration_minutes})."
                    ),
                )
                effects.append(eff)
                duration = clamped

        # ── Rule 5: clamp to device hard limits ───────────────────────────────
        if duration is not None:
            clamped_dev = max(device_min_minutes, min(duration, device_max_minutes))
            if clamped_dev != duration:
                eff = RuleEffect(
                    rule_id="clamp_runtime_bounds",
                    matched=True,
                    original_action=action,
                    final_action=action,
                    original_duration=duration,
                    final_duration=clamped_dev,
                    detail=f"Duration clamped to device limits [{device_min_minutes}, {device_max_minutes}].",
                )
                effects.append(eff)
                duration = clamped_dev

        return RuleEngineResult(
            final_action=action,
            final_duration_minutes=duration,
            effects=effects,
            overridden=bool(effects),
        )
