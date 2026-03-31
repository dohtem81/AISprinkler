"""LangChain-based implementation of AgentPort.

Supported providers (set via LLM_PROVIDER env var or the ``provider`` parameter):
  - ``openai``    – OpenAI Chat models (requires OPENAI_API_KEY)
  - ``anthropic`` – Anthropic Claude models (requires ANTHROPIC_API_KEY)
  - ``ollama``    – Local Ollama server (requires OLLAMA_BASE_URL, no API key needed)
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any
from uuid import UUID

from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)
from aisprinkler.domain.value_objects.weather_context import WeatherContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default model names per provider – can be overridden via constructor args
# or the LLM_MODEL env var.
# ---------------------------------------------------------------------------
_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4.1",
    "anthropic": "claude-3-7-sonnet",
    "ollama": "llama3.2",
}

_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"


def _build_llm(
    provider: str,
    model_name: str,
    temperature: float,
    ollama_base_url: str,
) -> Any:
    """Instantiate the correct LangChain chat model for *provider*.

    Import is deferred to avoid hard failures when optional API keys are absent
    for providers not in use (e.g. no ``OPENAI_API_KEY`` when using Ollama).
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(model=model_name, temperature=temperature)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(model=model_name, temperature=temperature)  # type: ignore[call-arg]

    if provider == "ollama":
        from langchain_ollama import ChatOllama  # noqa: PLC0415

        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=ollama_base_url,
        )

    raise ValueError(
        f"Unknown LLM provider '{provider}'. "
        "Supported values: openai, anthropic, ollama"
    )


class LangChainAgentAdapter(AgentPort):
    """Wraps a LangChain ReAct agent to implement AgentPort.

    Provider selection (in priority order):
    1. ``provider`` constructor argument
    2. ``LLM_PROVIDER`` environment variable
    3. Falls back to ``openai``

    Model name selection (in priority order):
    1. ``model_name`` constructor argument
    2. ``LLM_MODEL`` environment variable
    3. Provider-specific default (see ``_DEFAULT_MODELS``)
    """

    def __init__(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.2,
        max_iterations: int = 5,
        timeout_ms: int = 15_000,
        ollama_base_url: str | None = None,
    ) -> None:
        self._provider = (
            provider
            or os.getenv("LLM_PROVIDER", "openai")
        ).lower()
        self._model_name = (
            model_name
            or os.getenv("LLM_MODEL")
            or _DEFAULT_MODELS.get(self._provider, "gpt-4.1")
        )
        self._temperature = temperature
        self._max_iterations = max_iterations
        self._timeout_ms = timeout_ms
        self._ollama_base_url = (
            ollama_base_url
            or os.getenv("OLLAMA_BASE_URL", _OLLAMA_DEFAULT_BASE_URL)
        )
        # TODO: initialise full LangChain ReAct chain here

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
