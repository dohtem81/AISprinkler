"""AgentPort – interface that the LangChain adapter must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from aisprinkler.domain.value_objects.recommendation import Recommendation
from aisprinkler.domain.value_objects.weather_context import WeatherContext


class AgentPort(ABC):
    @abstractmethod
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
        """Invoke the AI agent and return a structured recommendation.

        Must raise ValueError if the agent response fails schema validation
        after all configured retries.
        """
        ...
