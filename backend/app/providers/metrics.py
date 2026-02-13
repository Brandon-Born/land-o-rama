from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.core.config import Settings
from app.providers.mock_data import CountyMetric, mock_market_metrics


class MarketMetricsProvider(Protocol):
    provider_name: str

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:
        """Fetch county-level market metrics for the requested state/counties."""


@dataclass(slots=True)
class MockMarketMetricsProvider:
    provider_name: str = "mock_market_metrics"

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:
        metrics = mock_market_metrics(as_of_date=as_of_date, state=state)
        if not counties:
            return metrics
        county_set = {county.lower() for county in counties}
        return [metric for metric in metrics if metric.county.lower() in county_set]


def build_market_metrics_provider(settings: Settings) -> MarketMetricsProvider:
    _ = settings
    # RapidAPI metrics are deprecated; runtime uses local/mock metrics provider.
    return MockMarketMetricsProvider()
