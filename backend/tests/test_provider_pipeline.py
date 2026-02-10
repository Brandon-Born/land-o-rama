from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import ConfigKV, MarketMetricDaily, ProviderRunEvent, SyncRun
from app.providers.mock_data import CandidateRecord, CountyMetric
from app.providers.rapidapi_listings import RapidAPIListingProvider
from app.providers.rapidapi_metrics import RapidAPIMarketMetricsProvider
from app.services.pipeline import run_daily_pipeline
from app.services.settings import ensure_default_settings


class FailingListingProvider:
    provider_name = "failing_listing_provider"

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        raise RuntimeError("listing provider outage")


class EmptyListingProvider:
    provider_name = "empty_listing_provider"

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        return []


class NoopEnrichmentProvider:
    provider_name = "noop_enrichment_provider"

    def enrich(self, candidate: CandidateRecord) -> CandidateRecord:
        return candidate


class StaticListingProvider:
    provider_name = "static_listing_provider"

    def fetch(self, state: str, max_price: float) -> list[CandidateRecord]:  # noqa: ARG002
        return [
            CandidateRecord(
                source_type="listing",
                source=self.provider_name,
                external_id="LIST-1",
                parcel_key="TX-TRAVIS-STATIC-1",
                county="Travis",
                state=state,
                price=3200.0,
                acreage=0.25,
                latitude=30.27,
                longitude=-97.74,
                zoning="residential",
                legal_access=True,
                utilities_hint="nearby",
                flood_risk_level=2,
                wetland_risk_level=1,
                road_distance_miles=0.4,
                days_on_market=18,
                price_per_acre=12800.0,
            )
        ]


class FailingMetricsProvider:
    provider_name = "failing_metrics_provider"

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:  # noqa: ARG002
        raise RuntimeError("metrics provider outage")


class EmptyMetricsProvider:
    provider_name = "empty_metrics_provider"

    def fetch(self, *, state: str, counties: list[str], as_of_date: date) -> list[CountyMetric]:  # noqa: ARG002
        return []


def test_missing_provider_keys_does_not_crash_app_startup() -> None:
    app = create_app(enable_startup_tasks=False, enable_scheduler=False, bootstrap_pipeline=False)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_live_listing_failure_marks_run_degraded(session_factory) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        run = run_daily_pipeline(
            db,
            listing_provider=FailingListingProvider(),
            enrichment_provider=NoopEnrichmentProvider(),
        )
        assert run.status == "degraded"

        events = db.scalars(
            select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)
        ).all()
        assert any(event.provider == "failing_listing_provider" and event.status == "failed" for event in events)


def test_full_provider_outage_with_no_fallback_candidates_fails_run(session_factory, monkeypatch) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        monkeypatch.setattr("app.services.pipeline.mock_candidates", lambda state: [])

        with pytest.raises(RuntimeError):
            run_daily_pipeline(
                db,
                listing_provider=EmptyListingProvider(),
                enrichment_provider=NoopEnrichmentProvider(),
            )

        latest_event = db.scalar(select(ProviderRunEvent).order_by(ProviderRunEvent.created_at.desc()))
        assert latest_event is not None
        run = db.get(SyncRun, latest_event.run_id)
        assert run is not None
        assert run.status == "failed"


def test_rapidapi_retry_attempts_and_last_error(monkeypatch) -> None:
    provider = RapidAPIListingProvider(
        api_key="key",
        host="example.test",
        provider_slug="mock-feed",
        timeout_seconds=1.0,
        max_retries=3,
    )

    call_count = {"count": 0}

    class DummyClient:
        def __init__(self, timeout: float):  # noqa: ARG002
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ARG002
            return False

        def get(self, url: str, headers: dict, params: dict):  # noqa: ARG002
            call_count["count"] += 1
            raise httpx.ConnectError("network down")

    monkeypatch.setattr("app.providers.rapidapi_listings.httpx.Client", DummyClient)

    with pytest.raises(RuntimeError) as exc_info:
        provider.fetch(state="TX", max_price=5000)

    assert call_count["count"] == 3
    assert "network down" in str(exc_info.value)


def test_live_metrics_failure_uses_cache_and_marks_run_degraded(session_factory, monkeypatch) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.add(
            MarketMetricDaily(
                county="Travis",
                state="TX",
                as_of_date=date.today() - timedelta(days=1),
                population_growth_1y=2.0,
                jobs_growth_1y=1.8,
                permit_growth_1y=2.2,
                turnover_index=62.0,
            )
        )
        db.commit()

        monkeypatch.setattr("app.services.pipeline.mock_candidates", lambda state: [])

        run = run_daily_pipeline(
            db,
            listing_provider=StaticListingProvider(),
            enrichment_provider=NoopEnrichmentProvider(),
            metrics_provider=FailingMetricsProvider(),
        )
        assert run.status == "degraded"

        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "failing_metrics_provider" and event.status == "failed" for event in events)
        assert any(event.provider == "market_metrics_cache" and event.status == "degraded" for event in events)


def test_live_metrics_missing_cache_uses_fallback_metric(session_factory, monkeypatch) -> None:
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

        monkeypatch.setattr("app.services.pipeline.mock_candidates", lambda state: [])

        run = run_daily_pipeline(
            db,
            listing_provider=StaticListingProvider(),
            enrichment_provider=NoopEnrichmentProvider(),
            metrics_provider=EmptyMetricsProvider(),
        )
        assert run.status == "degraded"
        assert run.candidates_scored > 0

        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "market_metrics_cache" and event.status == "failed" for event in events)
        assert any(event.provider == "market_metrics_fallback" and event.status == "degraded" for event in events)


def test_rapidapi_metrics_retry_attempts_and_last_error(monkeypatch) -> None:
    provider = RapidAPIMarketMetricsProvider(
        api_key="key",
        host="example.test",
        provider_slug="metrics-feed",
        timeout_seconds=1.0,
        max_retries=3,
    )

    call_count = {"count": 0}

    class DummyClient:
        def __init__(self, timeout: float):  # noqa: ARG002
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ARG002
            return False

        def get(self, url: str, headers: dict, params: dict):  # noqa: ARG002
            call_count["count"] += 1
            raise httpx.ConnectError("metrics network down")

    monkeypatch.setattr("app.providers.rapidapi_metrics.httpx.Client", DummyClient)

    with pytest.raises(RuntimeError) as exc_info:
        provider.fetch(state="TX", counties=["Travis"], as_of_date=date.today())

    assert call_count["count"] == 3
    assert "metrics network down" in str(exc_info.value)


def test_rapidapi_metrics_parses_list_payload(monkeypatch) -> None:
    provider = RapidAPIMarketMetricsProvider(
        api_key="key",
        host="example.test",
        provider_slug="metrics-feed",
        timeout_seconds=1.0,
        max_retries=1,
    )

    class DummyResponse:
        def raise_for_status(self) -> None:
            return

        def json(self):
            return {
                "results": [
                    {
                        "county": "travis",
                        "population_growth_1y": "2.5",
                        "jobs_growth_1y": "1.9",
                        "permit_growth_1y": "3.1",
                        "turnover_index": "61",
                    }
                ]
            }

    class DummyClient:
        def __init__(self, timeout: float):  # noqa: ARG002
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ARG002
            return False

        def get(self, url: str, headers: dict, params: dict):  # noqa: ARG002
            return DummyResponse()

    monkeypatch.setattr("app.providers.rapidapi_metrics.httpx.Client", DummyClient)

    metrics = provider.fetch(state="TX", counties=["Travis"], as_of_date=date(2026, 2, 10))
    assert len(metrics) == 1
    assert metrics[0].county == "Travis"
    assert metrics[0].population_growth_1y == pytest.approx(2.5)
    assert metrics[0].jobs_growth_1y == pytest.approx(1.9)
