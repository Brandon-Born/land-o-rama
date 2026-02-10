from __future__ import annotations


def _seed(client) -> None:
    response = client.post("/api/v1/jobs/run-daily")
    assert response.status_code == 200


def test_opportunity_list_excludes_excluded_records(client) -> None:
    _seed(client)
    response = client.get("/api/v1/opportunities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["total"] == len(payload["items"])
    assert all(item["price"] <= 5000 for item in payload["items"])


def test_opportunity_detail_success_and_not_found(client) -> None:
    _seed(client)
    list_response = client.get("/api/v1/opportunities")
    first_id = list_response.json()["items"][0]["id"]

    detail_response = client.get(f"/api/v1/opportunities/{first_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == first_id
    assert detail["score_breakdown"]["final_score"] >= 0
    assert "source_name" in detail
    assert "source_url" in detail

    missing_response = client.get("/api/v1/opportunities/not-a-real-id")
    assert missing_response.status_code == 404


def test_opportunity_filters(client) -> None:
    _seed(client)
    filtered = client.get("/api/v1/opportunities?county=travis&min_score=70")
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["items"]
    assert all(item["county"].lower() == "travis" for item in payload["items"])
    assert all(item["final_score"] >= 70 for item in payload["items"])
