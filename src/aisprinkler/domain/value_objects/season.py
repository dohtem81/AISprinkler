"""Season value object – canonical season codes and classification logic."""

from __future__ import annotations

from enum import Enum


class SeasonCode(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"
    ALL = "all"

    @staticmethod
    def from_month(month: int) -> "SeasonCode":
        """Return the season for a given calendar month (1-12) per Alabama defaults.

        Spring : March – April   (3–4)
        Summer : May – September (5–9)
        Fall   : October – Nov   (10–11)
        Winter : December – Feb  (12–2)
        """
        if month in (3, 4):
            return SeasonCode.SPRING
        if 5 <= month <= 9:
            return SeasonCode.SUMMER
        if month in (10, 11):
            return SeasonCode.FALL
        return SeasonCode.WINTER  # 12, 1, 2
