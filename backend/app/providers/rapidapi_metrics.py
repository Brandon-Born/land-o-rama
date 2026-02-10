from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.providers.mock_data import CountyMetric


class RapidAPIMarketMetricsProvider:
    provider_name = "rapidapi_market_metrics"

    def __init__(
        self,
        *,
        api_key: str | None,
        host: str | None,
        provider_slug: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self.api_key = api_key
        self.host = host
        self.provider_slug = provider_slug
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:
        if not self.api_key or not self.host:
            raise RuntimeError("RapidAPI credentials are missing (LANDORAMA_RAPIDAPI_KEY/HOST).")

        url = f"https://{self.host}/{self.provider_slug}".rstrip("/")
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }
        params: dict[str, str] = {"state": state}
        if counties:
            params["counties"] = ",".join(sorted({county.strip() for county in counties if county.strip()}))

        last_error: Exception | None = None
        for _ in range(max(1, self.max_retries)):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    payload = response.json()
                return self._parse_payload(payload, state=state, as_of_date=as_of_date)
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        raise RuntimeError(f"RapidAPI market metrics fetch failed: {last_error}") from last_error

    def _parse_payload(self, payload: Any, *, state: str, as_of_date: date) -> list[CountyMetric]:
        raw_items: list[dict[str, Any]] = []
        if isinstance(payload, list):
            raw_items = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            for key in ("results", "items", "data", "metrics", "counties"):
                value = payload.get(key)
                if isinstance(value, list):
                    raw_items = [item for item in value if isinstance(item, dict)]
                    break
            if not raw_items and {"county", "population_growth_1y", "jobs_growth_1y"}.intersection(payload.keys()):
                raw_items = [payload]

        metrics: list[CountyMetric] = []
        for item in raw_items:
            county = str(item.get("county") or item.get("county_name") or "").strip()
            if not county:
                continue
            metrics.append(
                CountyMetric(
                    county=county.title(),
                    state=state,
                    as_of_date=as_of_date,
                    population_growth_1y=_as_float(item.get("population_growth_1y") or item.get("population_growth") or 0),
                    jobs_growth_1y=_as_float(item.get("jobs_growth_1y") or item.get("job_growth") or 0),
                    permit_growth_1y=_as_float(item.get("permit_growth_1y") or item.get("permit_growth") or 0),
                    turnover_index=_as_float(item.get("turnover_index") or item.get("turnover") or 0),
                )
            )
        return metrics


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("%", "").replace(",", "").strip())
    except ValueError:
        return 0.0
