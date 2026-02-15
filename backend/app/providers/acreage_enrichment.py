from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import urlopen

HUNT_CAD_QUERY_URL = (
    "https://services3.arcgis.com/GIIiqmeq0npieHV9/ArcGIS/rest/services/"
    "HuntCADWebService/FeatureServer/0/query"
)


def build_hunt_cad_acreage_resolver(*, timeout_seconds: float = 10.0):
    @lru_cache(maxsize=4096)
    def _resolve(parcel_key: str) -> float | None:
        candidate = str(parcel_key or "").strip()
        if not candidate:
            return None
        escaped = candidate.replace("'", "''")
        params = urlencode(
            {
                "where": f"prop_id_text='{escaped}'",
                "outFields": "prop_id_text,legal_acreage",
                "returnGeometry": "false",
                "f": "json",
            }
        )
        url = f"{HUNT_CAD_QUERY_URL}?{params}"
        try:
            with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            return None
        first = features[0]
        if not isinstance(first, dict):
            return None
        attrs = first.get("attributes")
        if not isinstance(attrs, dict):
            return None
        acreage = _as_float(attrs.get("legal_acreage"))
        return acreage if acreage > 0 else None

    return _resolve


def _as_float(value: object | None) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError:
        return 0.0
