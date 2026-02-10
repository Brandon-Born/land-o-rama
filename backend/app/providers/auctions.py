from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.core.config import Settings
from app.providers.mock_data import CandidateRecord, mock_candidates


class AuctionProvider(Protocol):
    provider_name: str

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:
        """Fetch auction candidates from upstream source."""


@dataclass(slots=True)
class AuctionFetchStats:
    scanned_rows: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    error_samples: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MockAuctionProvider:
    provider_name: str = "mock_auctions"
    last_stats: AuctionFetchStats = field(default_factory=AuctionFetchStats)

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:
        rows = [
            candidate
            for candidate in mock_candidates(state=state)
            if candidate.source_type == "auction" and candidate.price <= max_price
        ]
        self.last_stats = AuctionFetchStats(scanned_rows=len(rows), accepted_rows=len(rows))
        return rows


@dataclass(slots=True)
class CsvAuctionProvider:
    csv_dir: Path
    glob_pattern: str
    max_file_age_days: int
    provider_name: str = "csv_auctions"
    last_stats: AuctionFetchStats = field(default_factory=AuctionFetchStats)

    _ALIASES = {
        "auction_id": ["auction_id", "id", "sale_id"],
        "parcel_key": ["parcel_key", "parcel_id", "apn", "parcel"],
        "county": ["county", "county_name"],
        "state": ["state"],
        "price": ["price", "list_price", "winning_bid", "amount"],
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

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:
        self.last_stats = AuctionFetchStats()
        files = self._candidate_files()
        if not files:
            raise RuntimeError(
                f"No auction CSV files found in {self.csv_dir} matching {self.glob_pattern} "
                f"within {self.max_file_age_days} days."
            )

        candidates: list[CandidateRecord] = []
        seen_keys: set[tuple[str, str, str]] = set()

        for file_path in files:
            with file_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    self._reject(f"{file_path.name}: missing header row")
                    continue
                for row_idx, row in enumerate(reader, start=2):
                    self.last_stats.scanned_rows += 1
                    parsed, error = self._to_candidate(row=row, fallback_state=state)
                    if error:
                        self._reject(f"{file_path.name}:{row_idx} {error}")
                        continue
                    if parsed.price > max_price:
                        continue

                    dedupe_key = (parsed.state, parsed.parcel_key, parsed.external_id)
                    if dedupe_key in seen_keys:
                        self._reject(f"{file_path.name}:{row_idx} duplicate parcel/auction identity")
                        continue
                    seen_keys.add(dedupe_key)

                    candidates.append(parsed)
                    self.last_stats.accepted_rows += 1

        if not candidates and self.last_stats.rejected_rows > 0:
            raise RuntimeError(
                f"Auction CSV parsing failed. Rejected rows: {self.last_stats.rejected_rows}. "
                + " | ".join(self.last_stats.error_samples)
            )
        return candidates

    def _candidate_files(self) -> list[Path]:
        if not self.csv_dir.exists() or not self.csv_dir.is_dir():
            return []

        cutoff = datetime.now(UTC) - timedelta(days=max(0, self.max_file_age_days))
        files: list[Path] = []
        for path in sorted(self.csv_dir.glob(self.glob_pattern)):
            if not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified >= cutoff:
                files.append(path)
        return files

    def _to_candidate(self, *, row: dict[str, str], fallback_state: str) -> tuple[CandidateRecord | None, str | None]:
        auction_id = self._read(row, "auction_id")
        parcel_key = self._read(row, "parcel_key")
        county = self._read(row, "county")

        price = _as_float(self._read(row, "price"))
        acreage = _as_float(self._read(row, "acreage"))
        if not auction_id or not parcel_key or not county:
            return None, "missing required identity columns"
        if price <= 0 or acreage <= 0:
            return None, "price/acreage must be > 0"

        row_state = (self._read(row, "state") or fallback_state).strip().upper()
        latitude = _as_float(self._read(row, "latitude"))
        longitude = _as_float(self._read(row, "longitude"))

        zoning = self._read(row, "zoning") or "residential"
        legal_access = _as_bool(self._read(row, "legal_access"), default=True)
        utilities_hint = self._read(row, "utilities_hint") or "unknown"
        flood_risk_level = int(_as_float(self._read(row, "flood_risk_level")))
        wetland_risk_level = int(_as_float(self._read(row, "wetland_risk_level")))
        road_distance_miles = _as_float(self._read(row, "road_distance_miles") or "1.0")
        days_on_market = int(_as_float(self._read(row, "days_on_market") or "15"))

        price_per_acre = _as_float(self._read(row, "price_per_acre"))
        if price_per_acre <= 0:
            price_per_acre = price / acreage

        return (
            CandidateRecord(
                source_type="auction",
                source=self.provider_name,
                external_id=auction_id,
                parcel_key=parcel_key,
                county=county.title(),
                state=row_state,
                price=price,
                acreage=acreage,
                latitude=latitude,
                longitude=longitude,
                zoning=zoning,
                legal_access=legal_access,
                utilities_hint=utilities_hint,
                flood_risk_level=flood_risk_level,
                wetland_risk_level=wetland_risk_level,
                road_distance_miles=road_distance_miles,
                days_on_market=days_on_market,
                price_per_acre=price_per_acre,
                source_name=self._read(row, "source_name") or self.provider_name,
                source_url=self._read(row, "source_url") or None,
            ),
            None,
        )

    def _read(self, row: dict[str, str], canonical: str) -> str:
        for alias in self._ALIASES.get(canonical, [canonical]):
            if alias in row and row[alias] is not None:
                return str(row[alias]).strip()
        return ""

    def _reject(self, message: str) -> None:
        self.last_stats.rejected_rows += 1
        if len(self.last_stats.error_samples) < 3:
            self.last_stats.error_samples.append(message)


def build_auction_provider(settings: Settings) -> AuctionProvider:
    source_mode = settings.auction_source_mode.strip().lower()
    if settings.mock_mode or source_mode == "mock":
        return MockAuctionProvider()
    if source_mode == "csv":
        return CsvAuctionProvider(
            csv_dir=Path(settings.auction_csv_dir),
            glob_pattern=settings.auction_csv_glob,
            max_file_age_days=settings.auction_max_file_age_days,
        )
    raise RuntimeError(f"Unsupported LANDORAMA_AUCTION_SOURCE_MODE: {settings.auction_source_mode}")


def _as_float(value: str | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
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
