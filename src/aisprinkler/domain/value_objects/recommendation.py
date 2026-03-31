"""Recommendation value object – structured output returned by the AI agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RecommendationAction(str, Enum):
    KEEP = "keep"
    REDUCE = "reduce"
    SKIP = "skip"
    INCREASE = "increase"


@dataclass(frozen=True)
class Recommendation:
    """Immutable recommendation produced by the AI decision agent.

    This object is produced *before* deterministic rules are applied.
    The rule engine may clamp or override the action.
    """

    action: RecommendationAction
    recommended_duration_minutes: int | None
    confidence_score: float  # 0.0 – 1.0
    rationale: str
    assumptions: list[str] = field(default_factory=list)
    policy_version: str = "v1.0.0"
    prompt_version: str = "prompt.v1.0.0"
    model_name: str = ""
    model_version: str = ""
    weather_source_provider: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(
                f"confidence_score must be in [0, 1], got {self.confidence_score}"
            )
        if self.action != RecommendationAction.SKIP and self.recommended_duration_minutes is not None:
            if self.recommended_duration_minutes < 0:
                raise ValueError("recommended_duration_minutes cannot be negative")
