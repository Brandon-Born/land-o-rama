from __future__ import annotations


def test_latest_digest_404_when_empty(client) -> None:
    response = client.get("/api/v1/digests/latest")
    assert response.status_code == 404


def test_digests_available_after_run(client) -> None:
    run_response = client.post("/api/v1/jobs/run-daily")
    assert run_response.status_code == 200

    latest_response = client.get("/api/v1/digests/latest")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert "summary" in latest_payload
    assert isinstance(latest_payload["opportunity_ids"], list)

    history_response = client.get("/api/v1/digests")
    assert history_response.status_code == 200
    history = history_response.json()["items"]
    assert history
    assert history[0]["id"] == latest_payload["id"]
