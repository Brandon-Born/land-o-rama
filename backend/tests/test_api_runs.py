from __future__ import annotations


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
