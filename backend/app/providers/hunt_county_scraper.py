from __future__ import annotations

import csv
import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader

from app.providers.county_scrapers import CountyScrapeResult, ScrapeArtifact, utcnow
from app.providers.mock_data import CandidateRecord


@dataclass(slots=True)
class HuntCountyDownloadFirstScraper:
    source_urls: list[str]
    download_dir: Path
    timeout_seconds: float
    request_interval_ms: int
    allowed_hosts: set[str]
    parser_version_csv: str = "hunt_csv_v1"
    parser_version_pdf: str = "hunt_pdf_v1"
    provider_name: str = "hunt_county_scraper"
    source_name_pdf: str = "Hunt County Tax Resale PDF"

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
        "source_url": ["source_url", "url", "auction_url"],
    }

    def fetch(self, *, state: str, counties: list[str], max_price: float) -> CountyScrapeResult:
        target_counties = {county.strip().lower() for county in counties if county.strip()}
        hunt_enabled = any(
            county == "hunt" or county.startswith("hunt county") or "hunt county" in county
            for county in target_counties
        )
        if not hunt_enabled:
            return CountyScrapeResult(candidates=[], warnings=[], artifacts=[], attempted_sources=0, successful_sources=0)

        self.download_dir.mkdir(parents=True, exist_ok=True)

        attempted_sources = 0
        successful_sources = 0
        warnings: list[str] = []
        artifacts: list[ScrapeArtifact] = []
        candidates: list[CandidateRecord] = []
        seen_keys: set[tuple[str, str, str]] = set()

        for source_url in self.source_urls:
            attempted_sources += 1
            try:
                local_path = self._download_to_local(source_url)
                parsed_rows, _accepted_pre_dedupe, rejected, parsed_candidates, parser_version = self._parse_source(
                    local_path,
                    state=state,
                    max_price=max_price,
                )
                accepted = 0
                dedupe_rejected = 0
                for candidate in parsed_candidates:
                    dedupe_key = (candidate.state, candidate.parcel_key, candidate.external_id)
                    if dedupe_key in seen_keys:
                        dedupe_rejected += 1
                        continue
                    seen_keys.add(dedupe_key)
                    candidates.append(candidate)
                    accepted += 1
                checksum = _sha256(local_path.read_bytes())
                artifacts.append(
                    ScrapeArtifact(
                        county="Hunt",
                        state=state,
                        source_url=source_url,
                        local_path=str(local_path),
                        fetched_at=utcnow(),
                        parser_version=parser_version,
                        checksum_sha256=checksum,
                        records_found=parsed_rows,
                        records_accepted=accepted,
                        records_rejected=rejected + dedupe_rejected,
                    )
                )
                successful_sources += 1
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{source_url}: {exc}")
            if self.request_interval_ms > 0:
                time.sleep(self.request_interval_ms / 1000.0)

        return CountyScrapeResult(
            candidates=candidates,
            warnings=warnings,
            artifacts=artifacts,
            attempted_sources=attempted_sources,
            successful_sources=successful_sources,
        )

    def _download_to_local(self, source_url: str) -> Path:
        parsed = urlparse(source_url)
        if parsed.scheme in {"", "file"}:
            if parsed.scheme == "file":
                source_path = Path(parsed.path)
            else:
                source_path = Path(source_url)
            if not source_path.exists():
                raise RuntimeError(f"Source file does not exist: {source_path}")
            target_path = self.download_dir / source_path.name
            target_path.write_bytes(source_path.read_bytes())
            return target_path

        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError(f"Unsupported source URL scheme: {parsed.scheme}")
        host = (parsed.hostname or "").lower()
        if self.allowed_hosts and host not in self.allowed_hosts:
            raise RuntimeError(f"Host is not allowlisted: {host}")

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(source_url)
            response.raise_for_status()
            content = response.content
        filename = Path(parsed.path or "hunt_source.csv").name or "hunt_source.csv"
        target_path = self.download_dir / filename
        target_path.write_bytes(content)
        return target_path

    def _parse_source(
        self,
        file_path: Path,
        *,
        state: str,
        max_price: float,
    ) -> tuple[int, int, int, list[CandidateRecord], str]:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            parsed_rows, accepted, rejected, candidates = self._parse_csv(file_path, state=state, max_price=max_price)
            return parsed_rows, accepted, rejected, candidates, self.parser_version_csv
        if suffix == ".pdf":
            parsed_rows, accepted, rejected, candidates = self._parse_pdf(file_path, state=state, max_price=max_price)
            return parsed_rows, accepted, rejected, candidates, self.parser_version_pdf
        raise RuntimeError(f"Unsupported file extension for Hunt parser: {file_path.suffix}")

    def _parse_csv(self, file_path: Path, *, state: str, max_price: float) -> tuple[int, int, int, list[CandidateRecord]]:
        parsed_rows = 0
        accepted = 0
        rejected = 0
        candidates: list[CandidateRecord] = []
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise RuntimeError("Missing CSV header row.")
            for row in reader:
                parsed_rows += 1
                parsed = self._to_candidate(row=row, fallback_state=state)
                if parsed is None:
                    rejected += 1
                    continue
                if parsed.price > max_price:
                    continue
                accepted += 1
                candidates.append(parsed)
        return parsed_rows, accepted, rejected, candidates

    def _parse_pdf(self, file_path: Path, *, state: str, max_price: float) -> tuple[int, int, int, list[CandidateRecord]]:
        text = self._extract_pdf_text(file_path)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Unable to extract text from Hunt PDF.")
        prop_row_pattern = re.compile(r"^(?P<prop_id>\d{5,})(?:\s+|$)")
        acres_pattern = re.compile(r"ACRES?\s*(?P<acreage>\d*\.?\d+)", re.IGNORECASE)
        money_pattern = re.compile(r"\$\s*(?P<market_value>[0-9,]+\.\d{2})")

        prop_indices = [
            idx
            for idx, line in enumerate(lines)
            if prop_row_pattern.match(line)
        ]
        if not prop_indices:
            raise RuntimeError("No parseable Hunt resale rows were found in PDF source.")

        parsed_rows = 0
        accepted = 0
        rejected = 0
        candidates: list[CandidateRecord] = []
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

            candidate = CandidateRecord(
                source_type="auction",
                source=self.provider_name,
                external_id=f"HUNT-{prop_id}",
                parcel_key=f"HUNT-{prop_id}",
                county="Hunt",
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
                source_name=self.source_name_pdf,
                source_url=None,
            )
            if candidate.price > max_price:
                continue
            accepted += 1
            candidates.append(candidate)

        return parsed_rows, accepted, rejected, candidates

    def _extract_pdf_text(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        text_parts: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                text_parts.append(extracted)
        return "\n".join(text_parts)

    def _to_candidate(self, *, row: dict[str, str], fallback_state: str) -> CandidateRecord | None:
        auction_id = self._read(row, "auction_id")
        parcel_key = self._read(row, "parcel_key")
        county = self._read(row, "county") or "Hunt"
        price = _as_float(self._read(row, "price"))
        acreage = _as_float(self._read(row, "acreage"))
        if not auction_id or not parcel_key or price <= 0 or acreage <= 0:
            return None

        row_state = (self._read(row, "state") or fallback_state).strip().upper()
        source_url = self._read(row, "source_url")
        source_name = self._read(row, "source_name") or "Hunt County Auction"
        price_per_acre = _as_float(self._read(row, "price_per_acre"))
        if price_per_acre <= 0:
            price_per_acre = price / acreage

        return CandidateRecord(
            source_type="auction",
            source=self.provider_name,
            external_id=auction_id,
            parcel_key=parcel_key,
            county=county.title(),
            state=row_state,
            price=price,
            acreage=acreage,
            latitude=_as_float(self._read(row, "latitude")),
            longitude=_as_float(self._read(row, "longitude")),
            zoning=self._read(row, "zoning") or "residential",
            legal_access=_as_bool(self._read(row, "legal_access"), default=True),
            utilities_hint=self._read(row, "utilities_hint") or "unknown",
            flood_risk_level=int(_as_float(self._read(row, "flood_risk_level"))),
            wetland_risk_level=int(_as_float(self._read(row, "wetland_risk_level"))),
            road_distance_miles=_as_float(self._read(row, "road_distance_miles") or "1.0"),
            days_on_market=int(_as_float(self._read(row, "days_on_market") or "10")),
            price_per_acre=price_per_acre,
            source_name=source_name,
            source_url=source_url or None,
        )

    def _read(self, row: dict[str, str], canonical: str) -> str:
        for alias in self._ALIASES.get(canonical, [canonical]):
            value = row.get(alias)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""


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


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
