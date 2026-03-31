"""WeatherPort – interface that infrastructure weather adapters must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from aisprinkler.domain.value_objects.weather_context import WeatherContext


class WeatherPort(ABC):
    @abstractmethod
    async def get_weather_context(
        self,
        device_id: UUID,
        as_of: datetime,
    ) -> WeatherContext:
        """Fetch and return a normalised WeatherContext for the given device and time.

        Implementations must handle primary/fallback provider selection and
        set WeatherContext.is_fallback_provider accordingly.
        """
        ...
