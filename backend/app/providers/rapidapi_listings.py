from __future__ import annotations

from dataclasses import replace
from typing import Any

import httpx

from app.providers.mock_data import CandidateRecord


class RapidAPIListingProvider:
    provider_name = "rapidapi_listings"

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

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:
        if not self.api_key or not self.host:
            raise RuntimeError("RapidAPI credentials are missing (LANDORAMA_RAPIDAPI_KEY/HOST).")

        url = f"https://{self.host}/{self.provider_slug}".rstrip("/")
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }
        params = {"state": state, "max_price": max_price, "property_type": "land"}

        last_error: Exception | None = None
        for _ in range(max(1, self.max_retries)):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    payload = response.json()
                return self._parse_payload(payload, state=state)
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        raise RuntimeError(f"RapidAPI fetch failed: {last_error}") from last_error

    def _parse_payload(self, payload: Any, *, state: str) -> list[CandidateRecord]:
        raw_items: list[dict[str, Any]] = []
        if isinstance(payload, list):
            raw_items = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            for key in ("results", "items", "data", "listings"):
                value = payload.get(key)
                if isinstance(value, list):
                    raw_items = [item for item in value if isinstance(item, dict)]
                    break

        candidates: list[CandidateRecord] = []
        for idx, item in enumerate(raw_items):
            parsed = self._to_candidate(item=item, idx=idx, state=state)
            if parsed:
                candidates.append(parsed)
        return candidates

    def _to_candidate(self, *, item: dict[str, Any], idx: int, state: str) -> CandidateRecord | None:
        external_id = str(item.get("id") or item.get("listing_id") or item.get("mls_id") or f"rapid-{idx}")
        county = str(item.get("county") or item.get("county_name") or "Unknown")

        price = _as_float(item.get("price") or item.get("list_price"))
        acreage = _as_float(item.get("acreage") or item.get("lot_size") or item.get("acres"))
        latitude = _as_float(item.get("latitude") or item.get("lat"))
        longitude = _as_float(item.get("longitude") or item.get("lng") or item.get("lon"))
        if price <= 0 or acreage <= 0:
            return None

        parcel_key = str(item.get("parcel_id") or item.get("apn") or f"{state}-{county}-{external_id}")
        candidate = CandidateRecord(
            source_type="listing",
            source=self.provider_name,
            external_id=external_id,
            parcel_key=parcel_key,
            county=county,
            state=state,
            price=price,
            acreage=acreage,
            latitude=latitude,
            longitude=longitude,
            zoning=str(item.get("zoning") or "residential"),
            legal_access=bool(item.get("legal_access", True)),
            utilities_hint=str(item.get("utilities_hint") or "unknown"),
            flood_risk_level=int(_as_float(item.get("flood_risk_level") or 0)),
            wetland_risk_level=int(_as_float(item.get("wetland_risk_level") or 0)),
            road_distance_miles=_as_float(item.get("road_distance_miles") or 1.0),
            days_on_market=int(_as_float(item.get("days_on_market") or 30)),
            price_per_acre=_as_float(item.get("price_per_acre") or (price / acreage)),
        )
        return replace(candidate, county=candidate.county.title())


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).replace("$", "").replace(",", "").strip()
        return float(text)
    except ValueError:
        return 0.0
