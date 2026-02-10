from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import ConfigKV, ProviderRunEvent, SyncRun
from app.providers.mock_data import CandidateRecord
from app.providers.rapidapi_listings import RapidAPIListingProvider
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
