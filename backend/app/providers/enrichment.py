from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.providers.mock_data import CandidateRecord
from app.providers.regrid_enrichment import RegridEnrichmentProvider


class ParcelEnrichmentProvider(Protocol):
    provider_name: str

    def enrich(self, candidate: CandidateRecord) -> CandidateRecord:
        """Attach parcel-level enrichment signals to a listing candidate."""


@dataclass(slots=True)
class NoopEnrichmentProvider:
    provider_name: str = "noop_enrichment"

    def enrich(self, candidate: CandidateRecord) -> CandidateRecord:
        return candidate


def build_enrichment_provider(settings: Settings) -> ParcelEnrichmentProvider:
    if settings.mock_mode:
        return NoopEnrichmentProvider(provider_name="mock_enrichment")
    return RegridEnrichmentProvider(
        api_key=settings.regrid_api_key,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )
