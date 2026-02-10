from __future__ import annotations

from dataclasses import replace
from typing import Any

import httpx

from app.providers.mock_data import CandidateRecord


class RegridEnrichmentProvider:
    provider_name = "regrid_enrichment"

    def __init__(self, *, api_key: str | None, timeout_seconds: float, max_retries: int) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def enrich(self, candidate: CandidateRecord) -> CandidateRecord:
        if not self.api_key:
            raise RuntimeError("Regrid API key missing (LANDORAMA_REGRID_API_KEY).")

        url = f"https://app.regrid.com/api/v1/parcels/{candidate.parcel_key}.json"
        params = {"token": self.api_key}

        last_error: Exception | None = None
        for _ in range(max(1, self.max_retries)):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                return self._merge(candidate, payload)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise RuntimeError(f"Regrid enrichment failed: {last_error}") from last_error

    def _merge(self, candidate: CandidateRecord, payload: dict[str, Any]) -> CandidateRecord:
        parcel = payload.get("parcel", payload) if isinstance(payload, dict) else {}
        if not isinstance(parcel, dict):
            return candidate

        zoning = str(parcel.get("zoning") or parcel.get("land_use") or candidate.zoning)
        legal_access = bool(parcel.get("legal_access", candidate.legal_access))
        utilities_hint = str(parcel.get("utilities_hint") or candidate.utilities_hint)

        flood_risk_level = int(_as_float(parcel.get("flood_risk_level") or candidate.flood_risk_level))
        wetland_risk_level = int(_as_float(parcel.get("wetland_risk_level") or candidate.wetland_risk_level))

        latitude = _as_float(parcel.get("latitude") or candidate.latitude)
        longitude = _as_float(parcel.get("longitude") or candidate.longitude)

        return replace(
            candidate,
            zoning=zoning,
            legal_access=legal_access,
            utilities_hint=utilities_hint,
            flood_risk_level=flood_risk_level,
            wetland_risk_level=wetland_risk_level,
            latitude=latitude,
            longitude=longitude,
        )


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return 0.0
