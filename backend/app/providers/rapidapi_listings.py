from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

import httpx

from app.providers.listing_types import ListingFetchResult, ListingScanConfig
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

    def fetch(self, scan: ListingScanConfig) -> ListingFetchResult:
        if not self.api_key or not self.host:
            raise RuntimeError("RapidAPI credentials are missing (LANDORAMA_RAPIDAPI_KEY/HOST).")
        if not scan.locations:
            raise RuntimeError("Listing scan locations are required for live mode.")

        url = f"https://{self.host}/{self.provider_slug}".rstrip("/")
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }
        candidates: list[CandidateRecord] = []
        warnings: list[str] = []
        attempted_requests = 0
        successful_requests = 0
        seen_keys: set[str] = set()

        for location in scan.locations:
            for page_idx in range(scan.pages_per_location):
                attempted_requests += 1
                params = {
                    "location": location,
                    "offset": page_idx * scan.offset_step,
                    "limit": scan.page_limit,
                    "property_type": scan.property_type,
                    "sort": scan.sort,
                    "price_max": scan.price_max,
                }
                payload, request_error = self._get_payload(url=url, headers=headers, params=params)
                if request_error is not None:
                    warnings.append(
                        f"location={location},offset={params['offset']},limit={scan.page_limit}: {request_error}"
                    )
                    continue
                successful_requests += 1
                parsed = self._parse_payload(payload, state=scan.state, fallback_location=location)
                for candidate in parsed:
                    dedupe_key = self._dedupe_key(candidate)
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)
                    candidates.append(candidate)

        if not candidates and warnings:
            raise RuntimeError(f"RapidAPI fetch failed for all listing requests: {warnings[0]}")

        return ListingFetchResult(
            candidates=candidates,
            warnings=warnings,
            attempted_requests=attempted_requests,
            successful_requests=successful_requests,
        )

    def _get_payload(self, *, url: str, headers: dict[str, str], params: dict[str, Any]) -> tuple[Any | None, str | None]:
        last_error: Exception | None = None
        for _ in range(max(1, self.max_retries)):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    return response.json(), None
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        return None, str(last_error)

    def _parse_payload(self, payload: Any, *, state: str, fallback_location: str) -> list[CandidateRecord]:
        raw_items: list[dict[str, Any]] = []
        if isinstance(payload, list):
            raw_items = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            for key in ("results", "items", "data", "listings"):
                value = payload.get(key)
                if isinstance(value, list):
                    raw_items = [item for item in value if isinstance(item, dict)]
                    break
            if not raw_items:
                home_search = payload.get("home_search")
                if isinstance(home_search, dict):
                    nested_results = home_search.get("results")
                    if isinstance(nested_results, list):
                        raw_items = [item for item in nested_results if isinstance(item, dict)]

        candidates: list[CandidateRecord] = []
        for idx, item in enumerate(raw_items):
            parsed = self._to_candidate(item=item, idx=idx, state=state, fallback_location=fallback_location)
            if parsed:
                candidates.append(parsed)
        return candidates

    def _to_candidate(
        self,
        *,
        item: dict[str, Any],
        idx: int,
        state: str,
        fallback_location: str,
    ) -> CandidateRecord | None:
        external_id = str(item.get("listing_id") or item.get("property_id") or item.get("id") or item.get("mls_id") or f"rapid-{idx}")
        county = str(item.get("county") or item.get("county_name") or fallback_location or "Unknown")

        raw_lot_sqft = (
            item.get("lot_sqft")
            or item.get("lot_size_sqft")
            or _dig(item, "description", "lot_sqft")
            or _dig(item, "description", "sqft")
            or _dig(item, "lot_size", "size")
        )
        price = _as_float(item.get("price") or item.get("list_price"))
        acreage = _as_float(item.get("acreage") or item.get("lot_size") or item.get("acres"))
        if acreage <= 0 and raw_lot_sqft:
            acreage = _as_float(raw_lot_sqft) / 43560.0

        latitude = _as_float(
            item.get("latitude")
            or item.get("lat")
            or _dig(item, "location", "address", "coordinate", "lat")
            or _dig(item, "location", "coordinate", "lat")
        )
        longitude = _as_float(
            item.get("longitude")
            or item.get("lng")
            or item.get("lon")
            or _dig(item, "location", "address", "coordinate", "lon")
            or _dig(item, "location", "coordinate", "lon")
        )
        if price <= 0 or acreage <= 0:
            return None

        parcel_key = str(item.get("parcel_id") or item.get("apn") or item.get("parcel_number") or f"{state}-{county}-{external_id}")
        source_name = str(
            item.get("source_name")
            or item.get("provider")
            or item.get("branding")
            or item.get("site_name")
            or item.get("marketplace")
            or "RapidAPI Listing Feed"
        )
        source_url = _first_text(
            item.get("url"),
            item.get("listing_url"),
            item.get("permalink"),
            item.get("property_url"),
            item.get("detail_url"),
            _dig(item, "href"),
        )
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
            source_name=source_name,
            source_url=source_url,
        )
        return replace(candidate, county=candidate.county.title())

    def _dedupe_key(self, candidate: CandidateRecord) -> str:
        if candidate.parcel_key:
            return f"parcel:{candidate.parcel_key.lower()}"
        if candidate.external_id:
            return f"source:{candidate.external_id.lower()}"
        fingerprint = f"{candidate.latitude:.5f}|{candidate.longitude:.5f}|{candidate.price:.2f}|{candidate.acreage:.4f}"
        return f"hash:{hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()}"


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


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _dig(payload: dict[str, Any], *path: str) -> Any | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
