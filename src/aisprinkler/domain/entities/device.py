"""Device entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Device:
    name: str
    device_type: str
    timezone: str
    location_lat: float
    location_lon: float
    id: UUID = field(default_factory=uuid4)
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_active(self) -> bool:
        return self.status == "active"

    def mark_inactive(self) -> None:
        self.status = "inactive"
        self.updated_at = datetime.now(timezone.utc)
