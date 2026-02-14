from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from app.providers.mock_data import CandidateRecord
from app.providers.source_catalog import ParserTemplateKey


@dataclass(slots=True)
class ParserTemplateResult:
    parser_version: str
    records_found: int
    records_accepted: int
    records_rejected: int
    candidates: list[CandidateRecord]
    parsed_prices: list[float]


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
        candidates: list[CandidateRecord] = []
        parsed_prices: list[float] = []
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise RuntimeError("Missing CSV header row.")
            for row in reader:
                parsed_rows += 1
                parsed = self._to_candidate(
                    row=row,
                    fallback_county=county,
                    fallback_state=state,
                    fallback_source_name=source_name or f"{county} County Auction",
                    provider_name=provider_name,
                )
                if parsed is None:
                    rejected += 1
                    continue
                parsed_prices.append(parsed.price)
                if parsed.price > max_price:
                    continue
                accepted += 1
                candidates.append(parsed)
        return ParserTemplateResult(
            parser_version=self.parser_version,
            records_found=parsed_rows,
            records_accepted=accepted,
            records_rejected=rejected,
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
    ) -> CandidateRecord | None:
        auction_id = self._read(row, "auction_id")
        parcel_key = self._read(row, "parcel_key")
        county = self._read(row, "county") or fallback_county
        price = _as_float(self._read(row, "price"))
        acreage = _as_float(self._read(row, "acreage"))
        if not auction_id or not parcel_key or price <= 0 or acreage <= 0:
            return None

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
        )

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
        money_pattern = re.compile(r"\$\s*(?P<market_value>[0-9,]+\.\d{2})")
        prop_indices = [idx for idx, line in enumerate(lines) if prop_row_pattern.match(line)]
        if not prop_indices:
            raise RuntimeError("No parseable tax-sale rows were found in PDF source.")

        parsed_rows = 0
        accepted = 0
        rejected = 0
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
            money_match = money_pattern.search(block)
            acreage = _as_float(acreage_match.group("acreage") if acreage_match else None)
            market_value = _as_float(money_match.group("market_value") if money_match else None)
            if acreage <= 0 or market_value <= 0:
                rejected += 1
                continue
            parsed_prices.append(market_value)

            candidate = CandidateRecord(
                source_type="auction",
                source=provider_name,
                external_id=f"{county.upper()}-{prop_id}",
                parcel_key=f"{county.upper()}-{prop_id}",
                county=county,
                state=fallback_state,
                price=market_value,
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
                price_per_acre=(market_value / acreage),
                source_name=fallback_source_name,
                source_url=None,
            )
            if candidate.price > max_price:
                continue
            accepted += 1
            candidates.append(candidate)

        return ParserTemplateResult(
            parser_version=self.parser_version,
            records_found=parsed_rows,
            records_accepted=accepted,
            records_rejected=rejected,
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


def get_parser_template(template_key: ParserTemplateKey) -> ParserTemplate:
    if template_key == "csv_taxsale_v1":
        return CsvTaxsaleParser()
    if template_key == "pdf_taxsale_v1":
        return PdfTaxsaleParser()
    if template_key == "html_table_taxsale_v1":
        return HtmlTableTaxsaleParser()
    raise RuntimeError(f"Unsupported parser template key: {template_key}")


def _extract_pdf_text(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    text_parts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            text_parts.append(extracted)
    return "\n".join(text_parts)


def _as_float(value: str | None) -> float:
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
