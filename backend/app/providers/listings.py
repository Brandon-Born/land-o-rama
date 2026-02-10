from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.providers.mock_data import CandidateRecord, mock_candidates
from app.providers.rapidapi_listings import RapidAPIListingProvider


class ListingProvider(Protocol):
    provider_name: str

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:
        """Fetch listing candidates from an upstream source."""


@dataclass(slots=True)
class MockListingProvider:
    provider_name: str = "mock_listings"

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:
        return [
            candidate
            for candidate in mock_candidates(state=state)
            if candidate.source_type == "listing" and candidate.price <= max_price
        ]


def build_listing_provider(settings: Settings) -> ListingProvider:
    if settings.mock_mode:
        return MockListingProvider()
    return RapidAPIListingProvider(
        api_key=settings.rapidapi_key,
        host=settings.rapidapi_host,
        provider_slug=settings.rapidapi_provider_slug,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )
