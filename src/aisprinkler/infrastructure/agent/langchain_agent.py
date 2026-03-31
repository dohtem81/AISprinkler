"""LangChain-based implementation of AgentPort."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)
from aisprinkler.domain.value_objects.weather_context import WeatherContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NOTE: The actual LangChain wiring (model, tools, chain) is added when the
# infrastructure implementation sprint begins.  This stub satisfies the port
# contract so the application layer and tests can be exercised immediately.
# ---------------------------------------------------------------------------


class LangChainAgentAdapter(AgentPort):
    """Wraps a LangChain ReAct agent to implement AgentPort."""

    def __init__(
        self,
        model_name: str = "gpt-4.1",
        temperature: float = 0.2,
        max_iterations: int = 5,
        timeout_ms: int = 15_000,
    ) -> None:
        self._model_name = model_name
        self._temperature = temperature
        self._max_iterations = max_iterations
        self._timeout_ms = timeout_ms
        # TODO: initialise LangChain chain here

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
        # TODO: build LangChain input payload, invoke chain, parse output
        raise NotImplementedError(
            "LangChainAgentAdapter.recommend() is not yet implemented. "
            "Use a mock in tests."
        )

    def _parse_output(self, raw: str, policy_version: str, prompt_version: str) -> Recommendation:
        """Parse and validate raw JSON output from the LLM."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Agent returned invalid JSON: {exc}") from exc

        return Recommendation(
            action=RecommendationAction(data["recommendation_action"]),
            recommended_duration_minutes=data.get("recommended_duration_minutes"),
            confidence_score=float(data["confidence_score"]),
            rationale=data["rationale"],
            assumptions=data.get("assumptions", []),
            policy_version=data.get("policy_version", policy_version),
            prompt_version=prompt_version,
            model_name=self._model_name,
            model_version="",
            weather_source_provider=data.get("weather_source_summary", {}).get("provider", ""),
        )
