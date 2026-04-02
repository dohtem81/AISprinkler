"""Structured trace for an agent prompt/response exchange."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aisprinkler.domain.value_objects.recommendation import Recommendation


@dataclass(frozen=True)
class AgentDecisionTrace:
    recommendation: Recommendation
    prompt_text: str
    response_text: str
    request_payload: dict[str, Any] = field(default_factory=dict)
    response_payload: dict[str, Any] = field(default_factory=dict)
