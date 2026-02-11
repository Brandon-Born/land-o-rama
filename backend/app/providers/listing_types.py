from __future__ import annotations

from dataclasses import dataclass

from app.providers.mock_data import CandidateRecord


@dataclass(slots=True)
class ListingScanConfig:
    state: str
    locations: list[str]
    page_limit: int
    pages_per_location: int
    sort: str
    price_max: float
    property_type: str = "land"
    offset_step: int = 50


@dataclass(slots=True)
class ListingFetchResult:
    candidates: list[CandidateRecord]
    warnings: list[str]
    attempted_requests: int
    successful_requests: int
