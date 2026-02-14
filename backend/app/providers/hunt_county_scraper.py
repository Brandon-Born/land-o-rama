from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from urllib.parse import urlparse

import httpx

from app.providers.county_scrapers import CountyScrapeResult, ScrapeArtifact, utcnow
from app.providers.parser_templates import get_parser_template
from app.providers.source_catalog import CountySourceBinding, ParserTemplateKey


@dataclass(slots=True)
class TemplateCountyDownloadFirstScraper:
    county: str
    state: str
    source_bindings: list[CountySourceBinding]
    download_dir: Path
    timeout_seconds: float
    request_interval_ms: int
    default_allowed_hosts: set[str]
    provider_name: str = "county_auction_scraper"

    def fetch(self, *, max_price: float) -> CountyScrapeResult:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        attempted_sources = 0
        successful_sources = 0
        warnings: list[str] = []
        artifacts: list[ScrapeArtifact] = []
        candidates = []
        seen_keys: set[tuple[str, str, str]] = set()

        for binding in sorted(self.source_bindings, key=lambda item: item.priority):
            attempted_sources += 1
            source_url = binding.source_url
            try:
                local_path = self._download_to_local(
                    source_url=source_url,
                    allowed_hosts=set(binding.allowed_hosts) if binding.allowed_hosts else self.default_allowed_hosts,
                )
                parser = get_parser_template(binding.parser_template_key)
                parsed = parser.parse(
                    file_path=local_path,
                    county=self.county,
                    state=self.state,
                    max_price=max_price,
                    source_name=binding.source_name,
                    provider_name=self.provider_name,
                )

                accepted = 0
                dedupe_rejected = 0
                for candidate in parsed.candidates:
                    dedupe_key = (candidate.state, candidate.parcel_key, candidate.external_id)
                    if dedupe_key in seen_keys:
                        dedupe_rejected += 1
                        continue
                    seen_keys.add(dedupe_key)
                    candidates.append(candidate)
                    accepted += 1

                checksum = _sha256(local_path.read_bytes())
                parsed_prices = parsed.parsed_prices
                artifacts.append(
                    ScrapeArtifact(
                        county=self.county,
                        state=self.state,
                        source_url=source_url,
                        local_path=str(local_path),
                        fetched_at=utcnow(),
                        parser_version=parsed.parser_version,
                        checksum_sha256=checksum,
                        records_found=parsed.records_found,
                        records_accepted=accepted,
                        records_rejected=parsed.records_rejected + dedupe_rejected,
                        price_min=min(parsed_prices) if parsed_prices else None,
                        price_median=float(median(parsed_prices)) if parsed_prices else None,
                        price_max=max(parsed_prices) if parsed_prices else None,
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

    def _download_to_local(self, *, source_url: str, allowed_hosts: set[str]) -> Path:
        parsed = urlparse(source_url)
        if parsed.scheme in {"", "file"}:
            source_path = Path(parsed.path if parsed.scheme == "file" else source_url)
            if not source_path.exists():
                raise RuntimeError(f"Source file does not exist: {source_path}")
            target_path = self.download_dir / source_path.name
            target_path.write_bytes(source_path.read_bytes())
            return target_path

        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError(f"Unsupported source URL scheme: {parsed.scheme}")
        host = (parsed.hostname or "").lower()
        if allowed_hosts and host not in allowed_hosts:
            raise RuntimeError(f"Host is not allowlisted: {host}")

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(source_url)
            response.raise_for_status()
            content = response.content
        filename = Path(parsed.path or "county_source.dat").name or "county_source.dat"
        target_path = self.download_dir / filename
        target_path.write_bytes(content)
        return target_path


# Backward-compatibility wrapper retained for one release cycle.
@dataclass(slots=True)
class HuntCountyDownloadFirstScraper:
    source_urls: list[str]
    download_dir: Path
    timeout_seconds: float
    request_interval_ms: int
    allowed_hosts: set[str]
    provider_name: str = "county_auction_scraper"

    def fetch(self, *, state: str, counties: list[str], max_price: float) -> CountyScrapeResult:
        target_counties = {county.strip().lower() for county in counties if county.strip()}
        hunt_enabled = any(
            county == "hunt" or county.startswith("hunt county") or "hunt county" in county
            for county in target_counties
        )
        if not hunt_enabled:
            return CountyScrapeResult(candidates=[], warnings=[], artifacts=[], attempted_sources=0, successful_sources=0)

        bindings = [
            CountySourceBinding(
                source_url=url,
                parser_template_key=_infer_template(url),
                allowed_hosts=sorted(self.allowed_hosts),
                priority=100,
                source_name="Hunt County Source",
            )
            for url in self.source_urls
        ]
        delegate = TemplateCountyDownloadFirstScraper(
            county="Hunt",
            state=state.strip().upper(),
            source_bindings=bindings,
            download_dir=self.download_dir,
            timeout_seconds=self.timeout_seconds,
            request_interval_ms=self.request_interval_ms,
            default_allowed_hosts=self.allowed_hosts,
            provider_name=self.provider_name,
        )
        return delegate.fetch(max_price=max_price)


def _infer_template(source_url: str) -> ParserTemplateKey:
    suffix = Path(urlparse(source_url).path).suffix.lower()
    if suffix == ".pdf":
        return "pdf_taxsale_v1"
    if suffix == ".csv":
        return "csv_taxsale_v1"
    return "html_table_taxsale_v1"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
