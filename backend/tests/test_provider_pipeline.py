from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import ConfigKV, MarketMetricDaily, ProviderRunEvent
from app.providers.auctions import AuctionFetchStats, CsvAuctionProvider, ScraperAuctionProvider
from app.providers.county_registry import build_county_registry
from app.providers.county_scrapers import CountyScrapeResult
from app.providers.hunt_county_scraper import HuntCountyDownloadFirstScraper
from app.providers.mock_data import CandidateRecord, CountyMetric
from app.services.pipeline import run_daily_pipeline
from app.services.settings import ensure_default_settings


class StaticAuctionProvider:
    provider_name = "county_auction_scraper"
    last_stats = AuctionFetchStats(scanned_rows=1, accepted_rows=1, rejected_rows=0)

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        return [
            CandidateRecord(
                source_type="auction",
                source=self.provider_name,
                external_id="AUC-STATIC-1",
                parcel_key="TX-HUNT-AUC-STATIC-1",
                county="Hunt",
                state=state,
                price=1800.0,
                acreage=0.30,
                latitude=33.1384,
                longitude=-96.1108,
                zoning="single_family",
                legal_access=True,
                utilities_hint="unknown",
                flood_risk_level=2,
                wetland_risk_level=1,
                road_distance_miles=0.5,
                days_on_market=7,
                price_per_acre=6000.0,
            )
        ]


class PartialAuctionProvider:
    provider_name = "county_auction_scraper"
    last_stats = AuctionFetchStats(
        scanned_rows=4,
        accepted_rows=2,
        rejected_rows=2,
        error_samples=["row 3 missing parcel_key", "row 6 invalid price"],
    )

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        return StaticAuctionProvider().fetch(state=state, max_price=max_price)


class FailingAuctionProvider:
    provider_name = "county_auction_scraper"
    last_stats = AuctionFetchStats(scanned_rows=0, accepted_rows=0, rejected_rows=0)

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        raise RuntimeError("hunt county source unavailable")


class EmptyAuctionProvider:
    provider_name = "county_auction_scraper"
    last_stats = AuctionFetchStats(scanned_rows=0, accepted_rows=0, rejected_rows=0)

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        return []


class FailingMetricsProvider:
    provider_name = "failing_metrics_provider"

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:  # noqa: ARG002
        raise RuntimeError("metrics provider outage")


class EmptyMetricsProvider:
    provider_name = "empty_metrics_provider"

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:  # noqa: ARG002
        return []


class StaticMetricsProvider:
    provider_name = "static_metrics_provider"

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:  # noqa: ARG002
        return [
            CountyMetric(
                county=county.title(),
                state=state,
                as_of_date=as_of_date,
                population_growth_1y=2.0,
                jobs_growth_1y=1.5,
                permit_growth_1y=2.2,
                turnover_index=60.0,
            )
            for county in counties
        ]


def test_missing_provider_keys_does_not_crash_app_startup() -> None:
    app = create_app(enable_startup_tasks=False, enable_scheduler=False, bootstrap_pipeline=False)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_no_auction_data_marks_run_degraded_and_carry_forward(session_factory) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        run = run_daily_pipeline(
            db,
            auction_provider=EmptyAuctionProvider(),
            metrics_provider=EmptyMetricsProvider(),
        )
        assert run.status == "degraded"
        assert run.candidates_scored == 0
        assert "No new auction candidates" in (run.error_summary or "")

        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "scraper_no_new_data" and event.status == "degraded" for event in events)


def test_live_metrics_failure_uses_cache_and_marks_run_degraded(session_factory) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.add(
            MarketMetricDaily(
                county="Hunt",
                state="TX",
                as_of_date=date.today() - timedelta(days=1),
                population_growth_1y=2.0,
                jobs_growth_1y=1.8,
                permit_growth_1y=2.2,
                turnover_index=62.0,
            )
        )
        db.commit()

        run = run_daily_pipeline(
            db,
            auction_provider=StaticAuctionProvider(),
            metrics_provider=FailingMetricsProvider(),
        )
        assert run.status == "degraded"
        assert run.candidates_scored > 0

        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "failing_metrics_provider" and event.status == "failed" for event in events)
        assert any(event.provider == "market_metrics_cache" and event.status == "degraded" for event in events)


def test_live_metrics_missing_cache_uses_fallback_metric(session_factory) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        run = run_daily_pipeline(
            db,
            auction_provider=StaticAuctionProvider(),
            metrics_provider=EmptyMetricsProvider(),
        )
        assert run.status == "degraded"
        assert run.candidates_scored > 0

        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "market_metrics_cache" and event.status == "failed" for event in events)
        assert any(event.provider == "market_metrics_fallback" and event.status == "degraded" for event in events)


def test_csv_auction_provider_parses_aliases_and_dedupes(tmp_path) -> None:
    csv_path = tmp_path / "county_sale.csv"
    csv_path.write_text(
        "\n".join(
            [
                "id,apn,county_name,state,winning_bid,acres,lat,lon,zoning,road_access,utilities,flood_risk,wetland_risk,road_distance,dom",
                "A1,PK-1,Hunt,TX,2100,0.25,33.1,-96.1,residential,true,nearby,2,1,0.5,10",
                "A1,PK-1,Hunt,TX,2100,0.25,33.1,-96.1,residential,true,nearby,2,1,0.5,10",
                "A2,,Hunt,TX,2200,0.30,33.2,-96.2,residential,true,nearby,2,1,0.5,12",
            ]
        ),
        encoding="utf-8",
    )

    provider = CsvAuctionProvider(csv_dir=tmp_path, glob_pattern="*.csv", max_file_age_days=30)
    candidates = provider.fetch(state="TX", max_price=5000)
    assert len(candidates) == 1
    assert candidates[0].external_id == "A1"
    assert provider.last_stats.rejected_rows == 2


def test_auction_partial_parse_marks_run_degraded(session_factory) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        run = run_daily_pipeline(
            db,
            auction_provider=PartialAuctionProvider(),
            metrics_provider=StaticMetricsProvider(),
        )
        assert run.status == "degraded"
        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "county_auction_scraper" and event.status == "degraded" for event in events)


def test_auction_failure_marks_run_degraded_no_new_data(session_factory) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        run = run_daily_pipeline(
            db,
            auction_provider=FailingAuctionProvider(),
            metrics_provider=StaticMetricsProvider(),
        )
        assert run.status == "degraded"
        assert run.auctions_ingested == 0
        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "county_auction_scraper" and event.status == "failed" for event in events)


def test_hunt_scraper_download_first_parses_local_csv_and_dedupes(tmp_path) -> None:
    source_csv = tmp_path / "hunt_source.csv"
    source_csv.write_text(
        "\n".join(
            [
                "auction_id,parcel_key,county,state,price,acreage,source_url",
                "H1,HK-1,Hunt,TX,1700,0.2,https://example.test/auctions/H1",
                "H1,HK-1,Hunt,TX,1700,0.2,https://example.test/auctions/H1",
                "H2,HK-2,Hunt,TX,7000,0.2,https://example.test/auctions/H2",
            ]
        ),
        encoding="utf-8",
    )
    scraper = HuntCountyDownloadFirstScraper(
        source_urls=[str(source_csv)],
        download_dir=tmp_path / "downloads",
        timeout_seconds=1.0,
        request_interval_ms=0,
        allowed_hosts=set(),
    )

    result = scraper.fetch(state="TX", counties=["Hunt County"], max_price=5000)
    assert result.attempted_sources == 1
    assert result.successful_sources == 1
    assert len(result.candidates) == 1
    assert result.candidates[0].external_id == "H1"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].records_found == 3
    assert result.artifacts[0].records_accepted == 1


def test_hunt_scraper_download_first_parses_pdf_and_filters(tmp_path, monkeypatch) -> None:
    source_pdf = tmp_path / "hunt_resale.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n%fixture\n")
    monkeypatch.setattr(
        "app.providers.parser_templates._extract_pdf_text",
        lambda _: (
            "25095 S4430 ORIG TOWN OF WOLFE CITY BLK 43 LOT 6A \n"
            "LOT 6 ACRES .2300 \n"
            "WOLFE CITY $5,780.00 \n"
            "25096 S4430 ORIG TOWN OF WOLFE CITY BLK 43 LOT 7A \n"
            "LOT 7 ACRES .5000 \n"
            "WOLFE CITY $12,000.00 \n"
            "25095 S4430 ORIG TOWN OF WOLFE CITY BLK 43 LOT 6A \n"
            "LOT 6 ACRES .2300 \n"
            "WOLFE CITY $5,780.00"
        ),
    )
    scraper = HuntCountyDownloadFirstScraper(
        source_urls=[str(source_pdf)],
        download_dir=tmp_path / "downloads",
        timeout_seconds=1.0,
        request_interval_ms=0,
        allowed_hosts=set(),
    )

    result = scraper.fetch(state="TX", counties=["Hunt County"], max_price=6000)
    assert result.attempted_sources == 1
    assert result.successful_sources == 1
    assert len(result.candidates) == 1
    assert result.artifacts[0].parser_version == "pdf_taxsale_v1"
    assert result.artifacts[0].records_found == 3
    assert result.artifacts[0].records_accepted == 1
    assert result.artifacts[0].records_rejected == 1


def test_hunt_scraper_template_mismatch_reports_warning(tmp_path) -> None:
    source_html = tmp_path / "county_source.html"
    source_html.write_text("<html><body>county source</body></html>", encoding="utf-8")
    scraper = HuntCountyDownloadFirstScraper(
        source_urls=[str(source_html)],
        download_dir=tmp_path / "downloads",
        timeout_seconds=1.0,
        request_interval_ms=0,
        allowed_hosts=set(),
    )

    result = scraper.fetch(state="TX", counties=["Hunt County"], max_price=6000)
    assert result.attempted_sources == 1
    assert result.successful_sources == 0
    assert not result.artifacts
    assert any("not implemented" in warning for warning in result.warnings)


def test_scraper_provider_raises_when_all_sources_fail() -> None:
    class FailingCountyScraper:
        provider_name = "hunt_county_scraper"

        def fetch(self, *, state: str, counties: list[str], max_price: float) -> CountyScrapeResult:  # noqa: ARG002
            return CountyScrapeResult(
                candidates=[],
                warnings=["dns lookup failed"],
                artifacts=[],
                attempted_sources=1,
                successful_sources=0,
            )

    provider = ScraperAuctionProvider(
        state="TX",
        counties=["Hunt County, TX"],
        scraper=FailingCountyScraper(),  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="dns lookup failed"):
        provider.fetch(state="TX", max_price=6000)
    assert provider.last_artifacts == []
    assert provider.last_stats.error_samples == ["dns lookup failed"]


def test_county_registry_enables_only_requested_targets(monkeypatch) -> None:
    monkeypatch.setenv("LANDORAMA_SCRAPER_TARGET_COUNTIES", "hunt,collin")
    from app.core.config import get_settings

    get_settings.cache_clear()
    registry = build_county_registry(get_settings())
    enabled = [entry.label for entry in registry if entry.enabled]
    assert "Hunt County, TX" in enabled
    assert "Collin County, TX" in enabled
    assert "Delta County, TX" not in enabled
    get_settings.cache_clear()
