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
from pathlib import Path
from typing import Any
from uuid import UUID

from aisprinkler.application.ports.agent_port import AgentPort
from aisprinkler.domain.value_objects.agent_decision_trace import AgentDecisionTrace
from aisprinkler.domain.value_objects.recommendation import (
    Recommendation,
    RecommendationAction,
)
from aisprinkler.domain.value_objects.weather_context import WeatherContext

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
_DEFAULT_RULES_FILE = "config/SPRINKLER_LLM_RULES.md"


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
        rules_file_path: str | None = None,
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
        self._rules_file_path = rules_file_path or os.getenv(
            "LLM_RULES_FILE", _DEFAULT_RULES_FILE
        )
        self._rules_text = self._load_rules_text(self._rules_file_path)
        self._llm = _build_llm(
            provider=self._provider,
            model_name=self._model_name,
            temperature=self._temperature,
            ollama_base_url=self._ollama_base_url,
        )

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
        request_payload = {
            "run_id": str(run_id),
            "correlation_id": str(correlation_id),
            "device_id": str(device_id),
            "baseline_duration_minutes": baseline_duration_minutes,
            "weather": {
                "rain_last_24h_mm": weather.rain_last_24h_mm,
                "rain_forecast_next_24h_mm": weather.rain_forecast_next_24h_mm,
                "rain_probability_pct": weather.rain_probability_pct,
                "temperature_c": weather.temperature_c,
                "humidity_pct": weather.humidity_pct,
                "wind_speed_kmh": weather.wind_speed_kmh,
                "provider": weather.provider,
                "is_fallback_provider": weather.is_fallback_provider,
            },
            "policy_version": policy_version,
            "prompt_version": prompt_version,
        }

        prompt_text = self._build_prompt(request_payload)
        logger.info(
            "Starting LLM recommendation call",
            extra={
                "action": "llm_call",
                "component": "llm",
                "status": "start",
                "model": self._model_name,
                "provider": self._provider,
                "run_id": str(run_id),
                "correlation_id": str(correlation_id),
                "prompt_summary": self._summarize_prompt(prompt_text),
                "prompt_chars": len(prompt_text),
            },
        )

        try:
            response = await self._llm.ainvoke(prompt_text)
        except Exception as exc:  # pragma: no cover - network/provider dependent
            logger.exception(
                "LLM call failed",
                extra={
                    "action": "llm_call",
                    "component": "llm",
                    "status": "failure",
                    "model": self._model_name,
                    "provider": self._provider,
                    "run_id": str(run_id),
                    "correlation_id": str(correlation_id),
                },
            )
            raise ValueError(f"Agent call failed: {exc}") from exc

        response_text = self._extract_response_text(response)
        recommendation = self._parse_output(response_text, policy_version, prompt_version)
        recommendation = self._coerce_recommendation(
            recommendation,
            baseline_duration_minutes,
            weather,
        )
        logger.info(
            "LLM recommendation completed",
            extra={
                "action": "llm_decision",
                "component": "llm",
                "status": "success",
                "model": self._model_name,
                "provider": self._provider,
                "run_id": str(run_id),
                "correlation_id": str(correlation_id),
                "decision": recommendation.action.value,
                "recommended_duration_minutes": recommendation.recommended_duration_minutes,
                "confidence_score": recommendation.confidence_score,
                "decision_summary": recommendation.rationale[:160],
            },
        )
        return AgentDecisionTrace(
            recommendation=recommendation,
            prompt_text=prompt_text,
            response_text=response_text,
            request_payload=request_payload,
            response_payload={
                "recommendation_action": recommendation.action.value,
                "recommended_duration_minutes": recommendation.recommended_duration_minutes,
                "confidence_score": recommendation.confidence_score,
                "rationale": recommendation.rationale,
            },
        )

    @staticmethod
    def _summarize_prompt(prompt: str) -> str:
        compact = " ".join(prompt.split())
        return compact[:180]

    @staticmethod
    def _load_rules_text(rules_file_path: str) -> str:
        candidate_paths = [
            Path(rules_file_path),
            Path.cwd() / rules_file_path,
            Path("/app") / rules_file_path,
            Path("/app/config/SPRINKLER_LLM_RULES.md"),
        ]
        for candidate in candidate_paths:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")

        logger.warning(
            "Rules file not found, using built-in fallback prompt",
            extra={
                "action": "llm_prompt",
                "component": "llm",
                "status": "fallback",
                "rules_file_path": rules_file_path,
            },
        )
        return (
            "Return JSON only with keys: recommendation_action, recommended_duration_minutes, "
            "confidence_score, rationale, assumptions, policy_version, weather_source_summary. "
            "recommendation_action must be one of keep|reduce|skip|increase. "
            "confidence_score must be float in [0,1]. "
            "If action is skip, recommended_duration_minutes must be null. "
            "weather_source_summary must include provider."
        )

    def _build_prompt(self, request_payload: dict[str, Any]) -> str:
        anti_copy_block = (
            "Critical constraints:\n"
            "1) Do not copy literal numbers or rationale text from examples in the rules document.\n"
            "2) Derive all values from Input payload only.\n"
            "3) recommendation_action must be one of keep|reduce|skip|increase.\n"
            "4) If recommendation_action is skip, recommended_duration_minutes must be null.\n"
            "5) confidence_score must be float in [0,1].\n"
            "6) Rationale must be numerically consistent with input weather signals.\n"
        )
        return (
            "You are an irrigation decision engine. Follow the rules document exactly. "
            "Return JSON only, no markdown, no extra prose.\n\n"
            f"{anti_copy_block}\n"
            "Rules document:\n"
            f"{self._rules_text}\n\n"
            "Input payload:\n"
            f"{json.dumps(request_payload, default=str)}"
        )

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict) and "text" in item:
                    chunks.append(str(item["text"]))
                else:
                    chunks.append(str(item))
            return "".join(chunks)
        return str(content)

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

    def _coerce_recommendation(
        self,
        recommendation: Recommendation,
        baseline_duration_minutes: int,
        weather: WeatherContext,
    ) -> Recommendation:
        """Apply safety/coherence corrections for low-quality model responses."""
        action = recommendation.action
        duration = recommendation.recommended_duration_minutes
        rationale = recommendation.rationale
        confidence = recommendation.confidence_score

        # If no baseline schedule exists for today, keep a safe zero-duration decision.
        if baseline_duration_minutes <= 0:
            logger.warning(
                "Coerced recommendation to baseline=0 safe keep",
                extra={
                    "action": "llm_decision_coerce",
                    "component": "llm",
                    "reason": "zero_baseline",
                    "original_action": recommendation.action.value,
                    "original_duration": recommendation.recommended_duration_minutes,
                },
            )
            return Recommendation(
                action=RecommendationAction.KEEP,
                recommended_duration_minutes=0,
                confidence_score=min(confidence, 0.75),
                rationale="No active baseline schedule for today; keeping safe duration at 0.",
                assumptions=recommendation.assumptions,
                policy_version=recommendation.policy_version,
                prompt_version=recommendation.prompt_version,
                model_name=recommendation.model_name,
                model_version=recommendation.model_version,
                weather_source_provider=recommendation.weather_source_provider,
            )

        dry_conditions = (
            weather.rain_last_24h_mm < 2.0
            and weather.rain_forecast_next_24h_mm < 2.0
            and weather.rain_probability_pct < 20.0
        )
        copied_example = (
            action == RecommendationAction.REDUCE
            and duration == 32
            and abs(confidence - 0.86) < 1e-9
            and "Observed rain was high and forecast remains wet" in rationale
        )
        if dry_conditions and copied_example:
            logger.warning(
                "Coerced copied-example recommendation under dry conditions",
                extra={
                    "action": "llm_decision_coerce",
                    "component": "llm",
                    "reason": "copied_example_dry_weather",
                },
            )
            return Recommendation(
                action=RecommendationAction.KEEP,
                recommended_duration_minutes=baseline_duration_minutes,
                confidence_score=min(confidence, 0.7),
                rationale=(
                    "Observed and forecast rain are low; keeping baseline duration "
                    "for this run."
                ),
                assumptions=recommendation.assumptions,
                policy_version=recommendation.policy_version,
                prompt_version=recommendation.prompt_version,
                model_name=recommendation.model_name,
                model_version=recommendation.model_version,
                weather_source_provider=recommendation.weather_source_provider,
            )

        # Normalize action-duration coherence without changing intent when possible.
        if action == RecommendationAction.SKIP:
            duration = None
        elif action == RecommendationAction.KEEP:
            duration = baseline_duration_minutes
        elif action == RecommendationAction.REDUCE:
            if duration is None:
                duration = max(0, int(round(baseline_duration_minutes * 0.9)))
            duration = min(duration, baseline_duration_minutes)
        elif action == RecommendationAction.INCREASE:
            if duration is None:
                duration = int(round(baseline_duration_minutes * 1.1))
            duration = max(duration, baseline_duration_minutes)

        if duration != recommendation.recommended_duration_minutes:
            logger.warning(
                "Normalized recommendation duration for action consistency",
                extra={
                    "action": "llm_decision_coerce",
                    "component": "llm",
                    "reason": "action_duration_consistency",
                    "original_duration": recommendation.recommended_duration_minutes,
                    "normalized_duration": duration,
                    "recommendation_action": action.value,
                },
            )

        return Recommendation(
            action=action,
            recommended_duration_minutes=duration,
            confidence_score=confidence,
            rationale=rationale,
            assumptions=recommendation.assumptions,
            policy_version=recommendation.policy_version,
            prompt_version=recommendation.prompt_version,
            model_name=recommendation.model_name,
            model_version=recommendation.model_version,
            weather_source_provider=recommendation.weather_source_provider,
        )
