from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class ProviderHealthStatus:
    provider: str
    status: str
    error_summary: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
