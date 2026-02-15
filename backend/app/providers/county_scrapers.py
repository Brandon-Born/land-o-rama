from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from app.providers.mock_data import CandidateRecord


@dataclass(slots=True)
class ScrapeArtifact:
    county: str
    state: str
    source_url: str
    local_path: str
    fetched_at: datetime
    parser_version: str
    checksum_sha256: str
    records_found: int
    records_accepted: int
    records_rejected: int
    records_filtered_price: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    price_min: float | None = None
    price_median: float | None = None
    price_max: float | None = None


@dataclass(slots=True)
class CountyScrapeResult:
    candidates: list[CandidateRecord]
    warnings: list[str]
    artifacts: list[ScrapeArtifact]
    attempted_sources: int
    successful_sources: int


class CountyAuctionScraperProvider(Protocol):
    provider_name: str

    def fetch(self, *, state: str, counties: list[str], max_price: float) -> CountyScrapeResult:
        """Fetch and parse county auction sources into canonical candidates."""


@dataclass(slots=True)
class NullCountyScraperProvider:
    provider_name: str = "null_county_scraper"

    def fetch(self, *, state: str, counties: list[str], max_price: float) -> CountyScrapeResult:  # noqa: ARG002
        return CountyScrapeResult(
            candidates=[],
            warnings=["No county scraper source URLs configured."],
            artifacts=[],
            attempted_sources=0,
            successful_sources=0,
        )


def utcnow() -> datetime:
    return datetime.now(UTC)
