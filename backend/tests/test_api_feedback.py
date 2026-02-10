from __future__ import annotations

from sqlalchemy import select

from app.models import Feedback


def test_feedback_submission_persists_vote(client, session_factory) -> None:
    client.post("/api/v1/jobs/run-daily")
    opportunity_id = client.get("/api/v1/opportunities").json()["items"][0]["id"]

    response = client.post(
        f"/api/v1/opportunities/{opportunity_id}/feedback",
        json={"vote": "up", "note": "integration test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["feedback_id"]

    with session_factory() as session:
        feedback = session.scalar(select(Feedback).where(Feedback.id == payload["feedback_id"]))
        assert feedback is not None
        assert feedback.vote == "up"


def test_feedback_404_for_unknown_opportunity(client) -> None:
    response = client.post(
        "/api/v1/opportunities/non-existent/feedback",
        json={"vote": "down"},
    )
    assert response.status_code == 404
