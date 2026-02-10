from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.models import Feedback, Opportunity, ProviderRunEvent
from app.services.personalization import count_labels, load_active_model, train_if_threshold_met
from app.services.pipeline import run_daily_pipeline
from app.services.settings import ensure_default_settings


def test_personalization_threshold_not_met_skips_training(session_factory, monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "pers.joblib"
    monkeypatch.setenv("LANDORAMA_PERSONALIZATION_MODEL_PATH", str(model_path))
    get_settings.cache_clear()

    with session_factory() as db:
        ensure_default_settings(db)
        run_daily_pipeline(db)

        opportunity_id = db.scalar(select(Opportunity.id).limit(1))
        assert opportunity_id is not None
        for _ in range(10):
            db.add(Feedback(opportunity_id=opportunity_id, vote="up"))
        db.commit()

        training_run = train_if_threshold_met(db)
        assert training_run is None
        assert count_labels(db) == 10
        assert not model_path.exists()
    get_settings.cache_clear()


def test_personalization_training_and_blend_applies(session_factory, monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "models" / "pers.joblib"
    monkeypatch.setenv("LANDORAMA_PERSONALIZATION_MODEL_PATH", str(model_path))
    get_settings.cache_clear()

    with session_factory() as db:
        ensure_default_settings(db)
        run_daily_pipeline(db)

        opportunity_id = db.scalar(select(Opportunity.id).limit(1))
        assert opportunity_id is not None

        for idx in range(50):
            vote = "up" if idx % 2 == 0 else "down"
            db.add(Feedback(opportunity_id=opportunity_id, vote=vote))
        db.commit()

        training_run = train_if_threshold_met(db)
        assert training_run is not None
        assert training_run.status == "success"
        assert training_run.labels_used >= 50
        assert model_path.exists()
        model = load_active_model()
        assert model is not None

        run = run_daily_pipeline(db)
        assert run.status in {"success", "degraded"}

        opportunities = db.scalars(
            select(Opportunity).where(Opportunity.run_id == run.id, Opportunity.is_excluded.is_(False))
        ).all()
        assert opportunities
        assert any(opp.personalization_score is not None for opp in opportunities)
        assert all(opp.blend_weight == get_settings().personalization_blend_weight for opp in opportunities)
        assert any(opp.model_version == training_run.model_version for opp in opportunities)

        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
        assert any(event.provider == "personalization_model" and event.status == "success" for event in events)
    get_settings.cache_clear()
