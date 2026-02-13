from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import ProviderRunEvent, SyncRun


def test_run_daily_creates_successful_run(client) -> None:
    run_response = client.post("/api/v1/jobs/run-daily")
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["status"] in {"success", "degraded"}
    assert payload["run_id"]

    runs_response = client.get("/api/v1/runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["items"]
    run = runs_payload["items"][0]
    assert run["id"] == payload["run_id"]
    assert run["status"] in {"success", "degraded", "failed"}
    assert run["listings_ingested"] >= 0
    assert run["auctions_ingested"] >= 0


def test_runs_endpoint_orders_provider_events_desc_for_degraded_run(client, session_factory) -> None:
    with session_factory() as session:
        run = SyncRun(
            run_type="daily",
            status="degraded",
            started_at=datetime.now(UTC) - timedelta(minutes=5),
            finished_at=datetime.now(UTC) - timedelta(minutes=4),
            listings_ingested=4,
            auctions_ingested=2,
            candidates_scored=6,
            excluded_count=1,
            error_summary="mixed provider degradation",
        )
        session.add(run)
        session.flush()
        run_id = run.id
        base = datetime.now(UTC)
        session.add_all(
            [
                ProviderRunEvent(run_id=run.id, provider="county_auction_scraper", status="failed", created_at=base),
                ProviderRunEvent(
                    run_id=run.id,
                    provider="csv_auctions",
                    status="degraded",
                    created_at=base + timedelta(seconds=1),
                ),
                ProviderRunEvent(
                    run_id=run.id,
                    provider="market_metrics_cache",
                    status="degraded",
                    created_at=base + timedelta(seconds=2),
                ),
            ]
        )
        session.commit()

    runs_response = client.get("/api/v1/runs")
    assert runs_response.status_code == 200
    items = runs_response.json()["items"]
    matching = next(item for item in items if item["id"] == run_id)
    assert matching["status"] == "degraded"
    assert matching["provider_events"][0]["provider"] == "market_metrics_cache"
    assert matching["provider_events"][1]["provider"] == "csv_auctions"
    assert matching["provider_events"][2]["provider"] == "county_auction_scraper"
