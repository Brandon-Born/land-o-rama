from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from pypdf import PdfReader

from app.providers.mock_data import CandidateRecord
from app.providers.parser_registry import ParserTemplateKey

_MONEY_PATTERN = re.compile(r"\$\s*(?P<amount>[0-9,]+(?:\.\d{2})?)")
_AUCTION_ENTRY_KEYWORDS = (
    "minimum bid",
    "min bid",
    "opening bid",
    "starting bid",
    "start bid",
    "bid amount",
    "base bid",
    "minimum offer",
    "minimum acceptable offer",
    "adjudged value",
    "amount due",
    "judgment amount",
    "tax due",
)
_MARKET_VALUE_KEYWORDS = (
    "market value",
    "appraised value",
    "assessed value",
    "market value-",
    "imp **market",
)
_LGBS_KEY_ALIASES = {
    "external_id": ["uid", "sale_id", "id", "property_sale_id", "property_id"],
    "parcel_key": [
        "parcel_key",
        "parcel_id",
        "account",
        "account_nbr",
        "account_number",
        "apn",
        "prop_id",
        "prop_id_text",
        "cad_id",
    ],
    "county": ["county", "county_name", "jurisdiction", "county_display"],
    "state": ["state", "state_code"],
    "acreage": ["acreage", "acres", "legal_acreage", "size_acres"],
    "auction_entry_price": [
        "minimum_bid",
        "min_bid",
        "opening_bid",
        "starting_bid",
        "bid_amount",
        "base_bid",
        "amount_due",
        "judgment_amount",
        "tax_due",
    ],
    "market_value": ["market_value", "appraised_value", "assessed_value", "value"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lng", "lon"],
    "source_url": ["source_url", "property_url", "detail_url", "url", "sale_url"],
    "source_name": ["source_name", "source", "provider_name"],
    "zoning": ["zoning", "land_use", "property_type"],
    "legal_access": ["legal_access", "road_access"],
    "utilities_hint": ["utilities_hint", "utilities"],
    "flood_risk_level": ["flood_risk_level", "flood_risk"],
    "wetland_risk_level": ["wetland_risk_level", "wetland_risk"],
    "road_distance_miles": ["road_distance_miles", "road_distance"],
    "days_on_market": ["days_on_market", "dom"],
    "price_per_acre": ["price_per_acre", "ppa"],
}


@dataclass(slots=True)
class ParserTemplateResult:
    parser_version: str
    records_found: int
    records_accepted: int
    records_rejected: int
    candidates: list[CandidateRecord]
    parsed_prices: list[float]
    records_filtered_price: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)


class ParserTemplate(Protocol):
    parser_version: str

    def parse(
        self,
        *,
        file_path: Path,
        county: str,
        state: str,
        max_price: float,
        source_name: str | None,
        provider_name: str,
    ) -> ParserTemplateResult:
        """Parse a source file and return canonical candidate records."""


@dataclass(slots=True)
class CsvTaxsaleParser:
    parser_version: str = "csv_taxsale_v1"

    _ALIASES = {
        "auction_id": ["auction_id", "id", "sale_id"],
        "parcel_key": ["parcel_key", "parcel_id", "apn", "parcel", "account"],
        "county": ["county", "county_name"],
        "state": ["state"],
        "price": ["price", "list_price", "winning_bid", "amount", "final_bid"],
        "acreage": ["acreage", "acres", "lot_size"],
        "latitude": ["latitude", "lat"],
        "longitude": ["longitude", "lng", "lon"],
        "zoning": ["zoning", "land_use"],
        "legal_access": ["legal_access", "road_access"],
        "utilities_hint": ["utilities_hint", "utilities"],
        "flood_risk_level": ["flood_risk_level", "flood_risk"],
        "wetland_risk_level": ["wetland_risk_level", "wetland_risk"],
        "road_distance_miles": ["road_distance_miles", "road_distance"],
        "days_on_market": ["days_on_market", "dom"],
        "price_per_acre": ["price_per_acre", "ppa"],
        "source_name": ["source_name", "site_name", "provider_name"],
        "source_url": ["source_url", "url", "auction_url", "listing_url"],
    }

    def parse(
        self,
        *,
        file_path: Path,
        county: str,
        state: str,
        max_price: float,
        source_name: str | None,
        provider_name: str,
    ) -> ParserTemplateResult:
        parsed_rows = 0
        accepted = 0
        rejected = 0
        filtered_price = 0
        rejection_reasons: dict[str, int] = {}
        candidates: list[CandidateRecord] = []
        parsed_prices: list[float] = []
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise RuntimeError("Missing CSV header row.")
            for row in reader:
                parsed_rows += 1
                parsed, reject_reason = self._to_candidate(
                    row=row,
                    fallback_county=county,
                    fallback_state=state,
                    fallback_source_name=source_name or f"{county} County Auction",
                    provider_name=provider_name,
                )
                if parsed is None:
                    rejected += 1
                    _increment_reason(rejection_reasons, reject_reason or "invalid_row")
                    continue
                parsed_prices.append(parsed.price)
                if parsed.price > max_price:
                    filtered_price += 1
                    _increment_reason(rejection_reasons, "price_cap")
                    continue
                accepted += 1
                candidates.append(parsed)
        return ParserTemplateResult(
            parser_version=self.parser_version,
            records_found=parsed_rows,
            records_accepted=accepted,
            records_rejected=rejected,
            records_filtered_price=filtered_price,
            rejection_reasons=rejection_reasons,
            candidates=candidates,
            parsed_prices=parsed_prices,
        )

    def _to_candidate(
        self,
        *,
        row: dict[str, str],
        fallback_county: str,
        fallback_state: str,
        fallback_source_name: str,
        provider_name: str,
    ) -> tuple[CandidateRecord | None, str | None]:
        auction_id = self._read(row, "auction_id")
        parcel_key = self._read(row, "parcel_key")
        county = self._read(row, "county") or fallback_county
        price = _as_float(self._read(row, "price"))
        acreage = _as_float(self._read(row, "acreage"))
        if not auction_id or not parcel_key or price <= 0 or acreage <= 0:
            return None, "missing_required_fields"

        row_state = (self._read(row, "state") or fallback_state).strip().upper()
        source_url = self._read(row, "source_url")
        source = self._read(row, "source_name") or fallback_source_name
        price_per_acre = _as_float(self._read(row, "price_per_acre"))
        if price_per_acre <= 0:
            price_per_acre = price / acreage

        return CandidateRecord(
            source_type="auction",
            source=provider_name,
            external_id=auction_id,
            parcel_key=parcel_key,
            county=county.title(),
            state=row_state,
            price=price,
            acreage=acreage,
            latitude=_as_float(self._read(row, "latitude")),
            longitude=_as_float(self._read(row, "longitude")),
            zoning=self._read(row, "zoning") or "unknown",
            legal_access=_as_bool(self._read(row, "legal_access"), default=True),
            utilities_hint=self._read(row, "utilities_hint") or "unknown",
            flood_risk_level=int(_as_float(self._read(row, "flood_risk_level"))),
            wetland_risk_level=int(_as_float(self._read(row, "wetland_risk_level"))),
            road_distance_miles=_as_float(self._read(row, "road_distance_miles") or "1.0"),
            days_on_market=int(_as_float(self._read(row, "days_on_market") or "10")),
            price_per_acre=price_per_acre,
            source_name=source,
            source_url=source_url or None,
        ), None

    def _read(self, row: dict[str, str], canonical: str) -> str:
        for alias in self._ALIASES.get(canonical, [canonical]):
            value = row.get(alias)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""


@dataclass(slots=True)
class PdfTaxsaleParser:
    parser_version: str = "pdf_taxsale_v1"

    def parse(
        self,
        *,
        file_path: Path,
        county: str,
        state: str,
        max_price: float,
        source_name: str | None,
        provider_name: str,
    ) -> ParserTemplateResult:
        lines = [line.strip() for line in _extract_pdf_text(file_path).splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Unable to extract text from tax-sale PDF.")

        prop_row_pattern = re.compile(r"^(?P<prop_id>\d{5,})(?:\s+|$)")
        acres_pattern = re.compile(r"ACRES?\s*(?P<acreage>\d*\.?\d+)", re.IGNORECASE)
        prop_indices = [idx for idx, line in enumerate(lines) if prop_row_pattern.match(line)]
        if not prop_indices:
            raise RuntimeError("No parseable tax-sale rows were found in PDF source.")

        parsed_rows = 0
        accepted = 0
        rejected = 0
        filtered_price = 0
        rejection_reasons: dict[str, int] = {}
        candidates: list[CandidateRecord] = []
        parsed_prices: list[float] = []
        fallback_source_name = source_name or f"{county} County Tax Resale PDF"
        fallback_state = state.strip().upper()
        for offset, start_idx in enumerate(prop_indices):
            end_idx = prop_indices[offset + 1] if offset + 1 < len(prop_indices) else len(lines)
            block = " ".join(lines[start_idx:end_idx])
            prop_match = prop_row_pattern.match(lines[start_idx])
            if prop_match is None:
                continue
            parsed_rows += 1

            prop_id = prop_match.group("prop_id")
            acreage_match = acres_pattern.search(block)
            acreage = _as_float(acreage_match.group("acreage") if acreage_match else None)
            auction_entry_price, market_value = _extract_block_prices(block)
            selected_price = auction_entry_price or market_value
            if acreage <= 0 or selected_price <= 0:
                rejected += 1
                _increment_reason(rejection_reasons, "missing_acreage_or_price")
                continue
            parsed_prices.append(selected_price)

            candidate = CandidateRecord(
                source_type="auction",
                source=provider_name,
                external_id=f"{county.upper()}-{prop_id}",
                parcel_key=f"{county.upper()}-{prop_id}",
                county=county,
                state=fallback_state,
                price=selected_price,
                acreage=acreage,
                latitude=0.0,
                longitude=0.0,
                zoning="unknown",
                legal_access=True,
                utilities_hint="unknown",
                flood_risk_level=0,
                wetland_risk_level=0,
                road_distance_miles=1.0,
                days_on_market=1,
                price_per_acre=(selected_price / acreage),
                source_name=fallback_source_name,
                source_url=None,
                auction_entry_price=auction_entry_price,
                observed_market_value=market_value,
                price_source="auction_entry_price" if auction_entry_price else "market_value_fallback",
            )
            if candidate.price > max_price:
                filtered_price += 1
                _increment_reason(rejection_reasons, "price_cap")
                continue
            accepted += 1
            candidates.append(candidate)

        return ParserTemplateResult(
            parser_version=self.parser_version,
            records_found=parsed_rows,
            records_accepted=accepted,
            records_rejected=rejected,
            records_filtered_price=filtered_price,
            rejection_reasons=rejection_reasons,
            candidates=candidates,
            parsed_prices=parsed_prices,
        )


@dataclass(slots=True)
class HtmlTableTaxsaleParser:
    parser_version: str = "html_table_taxsale_v1"

    def parse(
        self,
        *,
        file_path: Path,  # noqa: ARG002
        county: str,  # noqa: ARG002
        state: str,  # noqa: ARG002
        max_price: float,  # noqa: ARG002
        source_name: str | None,  # noqa: ARG002
        provider_name: str,  # noqa: ARG002
    ) -> ParserTemplateResult:
        raise RuntimeError("html_table_taxsale_v1 parser scaffold is not implemented yet.")


@dataclass(slots=True)
class LgbsPropertySalesParser:
    parser_version: str = "lgbs_property_sales_v1"
    hunt_acreage_resolver: Callable[[str], float | None] | None = None

    def parse(
        self,
        *,
        file_path: Path,
        county: str,
        state: str,
        max_price: float,
        source_name: str | None,
        provider_name: str,
    ) -> ParserTemplateResult:
        payload = _load_json_payload(file_path)
        rows = _extract_lgbs_rows(payload)
        if not rows:
            raise RuntimeError("No parseable property sale rows were found in LGBS source payload.")

        parsed_rows = 0
        accepted = 0
        rejected = 0
        filtered_price = 0
        rejection_reasons: dict[str, int] = {}
        candidates: list[CandidateRecord] = []
        parsed_prices: list[float] = []
        fallback_source_name = source_name or "LGBS Property Sales"
        fallback_state = state.strip().upper()
        fallback_county = county.strip().title()
        for row in rows:
            parsed_rows += 1
            candidate, reject_reason = self._to_candidate(
                row=row,
                fallback_county=fallback_county,
                fallback_state=fallback_state,
                fallback_source_name=fallback_source_name,
                provider_name=provider_name,
            )
            if candidate is None:
                rejected += 1
                _increment_reason(rejection_reasons, reject_reason or "invalid_row")
                continue
            parsed_prices.append(candidate.price)
            if candidate.price > max_price:
                filtered_price += 1
                _increment_reason(rejection_reasons, "price_cap")
                continue
            accepted += 1
            candidates.append(candidate)

        return ParserTemplateResult(
            parser_version=self.parser_version,
            records_found=parsed_rows,
            records_accepted=accepted,
            records_rejected=rejected,
            records_filtered_price=filtered_price,
            rejection_reasons=rejection_reasons,
            candidates=candidates,
            parsed_prices=parsed_prices,
        )

    def _to_candidate(
        self,
        *,
        row: dict[str, Any],
        fallback_county: str,
        fallback_state: str,
        fallback_source_name: str,
        provider_name: str,
    ) -> tuple[CandidateRecord | None, str | None]:
        lookup = _normalized_lookup(row)
        raw_county = _as_text(_read_any(lookup, _LGBS_KEY_ALIASES["county"]))
        normalized_fallback_county = _normalize_county_name(fallback_county)
        normalized_row_county = _normalize_county_name(raw_county) if raw_county else normalized_fallback_county
        county = normalized_row_county.title() if normalized_row_county else fallback_county
        if raw_county and normalized_row_county != normalized_fallback_county:
            return None, "county_mismatch"

        external_id = _as_text(_read_any(lookup, _LGBS_KEY_ALIASES["external_id"]))
        parcel_key = _as_text(_read_any(lookup, _LGBS_KEY_ALIASES["parcel_key"])) or external_id
        if not external_id:
            external_id = parcel_key
        if not external_id or not parcel_key:
            return None, "missing_identity"

        acreage = _as_float(_read_any(lookup, _LGBS_KEY_ALIASES["acreage"]))
        if acreage <= 0 and normalized_fallback_county == "hunt" and self.hunt_acreage_resolver is not None:
            acreage = self.hunt_acreage_resolver(parcel_key) or 0.0
        if acreage <= 0:
            return None, "missing_acreage"

        auction_entry_price = _as_float(_read_any(lookup, _LGBS_KEY_ALIASES["auction_entry_price"]))
        market_value = _as_float(_read_any(lookup, _LGBS_KEY_ALIASES["market_value"]))
        selected_price = auction_entry_price or market_value
        if selected_price <= 0:
            return None, "missing_price"

        state = _as_text(_read_any(lookup, _LGBS_KEY_ALIASES["state"])).upper() or fallback_state
        latitude, longitude = _extract_coordinates(row, lookup)
        if latitude is None:
            latitude = 0.0
        if longitude is None:
            longitude = 0.0

        source_url = _as_text(_read_any(lookup, _LGBS_KEY_ALIASES["source_url"])) or None
        source = _as_text(_read_any(lookup, _LGBS_KEY_ALIASES["source_name"])) or fallback_source_name
        price_per_acre = _as_float(_read_any(lookup, _LGBS_KEY_ALIASES["price_per_acre"]))
        if price_per_acre <= 0:
            price_per_acre = selected_price / acreage

        return CandidateRecord(
            source_type="auction",
            source=provider_name,
            external_id=external_id,
            parcel_key=parcel_key,
            county=county,
            state=state,
            price=selected_price,
            acreage=acreage,
            latitude=latitude,
            longitude=longitude,
            zoning=_as_text(_read_any(lookup, _LGBS_KEY_ALIASES["zoning"])) or "unknown",
            legal_access=_as_bool(_as_text(_read_any(lookup, _LGBS_KEY_ALIASES["legal_access"])), default=True),
            utilities_hint=_as_text(_read_any(lookup, _LGBS_KEY_ALIASES["utilities_hint"])) or "unknown",
            flood_risk_level=int(_as_float(_read_any(lookup, _LGBS_KEY_ALIASES["flood_risk_level"]))),
            wetland_risk_level=int(_as_float(_read_any(lookup, _LGBS_KEY_ALIASES["wetland_risk_level"]))),
            road_distance_miles=_as_float(_read_any(lookup, _LGBS_KEY_ALIASES["road_distance_miles"]) or "1.0"),
            days_on_market=int(_as_float(_read_any(lookup, _LGBS_KEY_ALIASES["days_on_market"]) or "1")),
            price_per_acre=price_per_acre,
            source_name=source,
            source_url=source_url,
            auction_entry_price=auction_entry_price if auction_entry_price > 0 else None,
            observed_market_value=market_value if market_value > 0 else None,
            price_source="auction_entry_price" if auction_entry_price > 0 else "market_value_fallback",
        ), None


def get_parser_template(
    template_key: ParserTemplateKey,
    *,
    hunt_acreage_resolver: Callable[[str], float | None] | None = None,
) -> ParserTemplate:
    if template_key == "csv_taxsale_v1":
        return CsvTaxsaleParser()
    if template_key == "pdf_taxsale_v1":
        return PdfTaxsaleParser()
    if template_key == "html_table_taxsale_v1":
        return HtmlTableTaxsaleParser()
    if template_key == "lgbs_property_sales_v1":
        return LgbsPropertySalesParser(hunt_acreage_resolver=hunt_acreage_resolver)
    raise RuntimeError(f"Unsupported parser template key: {template_key}")


def _extract_pdf_text(file_path: Path) -> str:
    if file_path.suffix.lower() in {".txt", ".text"}:
        return file_path.read_text(encoding="utf-8")
    reader = PdfReader(str(file_path))
    text_parts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            text_parts.append(extracted)
    return "\n".join(text_parts)


def _load_json_payload(file_path: Path) -> Any:
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON payload: {exc}") from exc


def _extract_lgbs_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("results"), list):
        return [item for item in payload["results"] if isinstance(item, dict)]
    if isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    if isinstance(payload.get("features"), list):
        rows: list[dict[str, Any]] = []
        for feature in payload["features"]:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                continue
            row = dict(properties)
            geometry = feature.get("geometry")
            if isinstance(geometry, dict) and "geometry" not in row:
                row["geometry"] = geometry
            rows.append(row)
        return rows
    if payload:
        return [payload]
    return []


def _normalized_lookup(row: dict[str, Any]) -> dict[str, Any]:
    return {_normalize_key(key): value for key, value in row.items()}


def _normalize_key(value: str) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _read_any(lookup: dict[str, Any], aliases: list[str]) -> Any:
    for alias in aliases:
        normalized = _normalize_key(alias)
        if normalized in lookup and lookup[normalized] not in (None, ""):
            return lookup[normalized]
    return None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_coordinates(row: dict[str, Any], lookup: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = _as_float(_read_any(lookup, _LGBS_KEY_ALIASES["latitude"]))
    lon = _as_float(_read_any(lookup, _LGBS_KEY_ALIASES["longitude"]))
    if lat != 0.0 or lon != 0.0:
        return lat, lon

    geometry = row.get("geometry")
    if isinstance(geometry, dict):
        coords = geometry.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            lon = _as_float(coords[0])
            lat = _as_float(coords[1])
            if lat != 0.0 or lon != 0.0:
                return lat, lon
    return None, None


def _normalize_county_name(value: str) -> str:
    normalized = _as_text(value).lower()
    normalized = normalized.replace("county", " ")
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = " ".join(normalized.split())
    return normalized


def _increment_reason(counter: dict[str, int], reason: str) -> None:
    counter[reason] = counter.get(reason, 0) + 1


def _extract_block_prices(block: str) -> tuple[float | None, float | None]:
    values = _extract_money_values(block)
    if not values:
        return None, None

    # Prefer context-labeled bid/entry amounts for filtering; keep market value separately for explainability.
    auction_entry_price = _pick_contextual_money_value(block, _AUCTION_ENTRY_KEYWORDS)
    market_value = _pick_contextual_money_value(block, _MARKET_VALUE_KEYWORDS)

    if auction_entry_price is None and len(values) > 1:
        market_value = market_value or values[0]
        for candidate in values:
            if market_value is None or abs(candidate - market_value) > 1e-9:
                auction_entry_price = candidate
                break

    if market_value is None:
        market_value = values[0]

    return auction_entry_price, market_value


def _extract_money_values(text: str) -> list[float]:
    amounts: list[float] = []
    for match in _MONEY_PATTERN.finditer(text):
        value = _as_float(match.group("amount"))
        if value > 0:
            amounts.append(value)
    return amounts


def _pick_contextual_money_value(
    block: str,
    keywords: tuple[str, ...],
) -> float | None:
    lowered = block.lower()
    keyword_after_matches: list[float] = []
    for match in _MONEY_PATTERN.finditer(block):
        amount = _as_float(match.group("amount"))
        if amount <= 0:
            continue
        before_context = lowered[max(0, match.start() - 64):match.start()]
        if any(keyword in before_context for keyword in keywords):
            return amount
        after_context = lowered[match.end():min(len(block), match.end() + 64)]
        if any(keyword in after_context for keyword in keywords):
            keyword_after_matches.append(amount)
    for keyword in keywords:
        keyword_index = lowered.find(keyword)
        if keyword_index < 0:
            continue
        start = max(0, keyword_index - 48)
        end = min(len(block), keyword_index + len(keyword) + 96)
        context = block[start:end]
        context_values = _extract_money_values(context)
        if context_values:
            return context_values[0]
    if keyword_after_matches:
        return keyword_after_matches[0]
    return None


def _as_float(value: Any | None) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError:
        return 0.0


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None or str(value).strip() == "":
        return default
    normalized = str(value).strip().lower()
    if normalized in {"true", "t", "1", "yes", "y"}:
        return True
    if normalized in {"false", "f", "0", "no", "n"}:
        return False
    return default
