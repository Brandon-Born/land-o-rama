from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.main import create_app


def test_alembic_upgrade_creates_required_tables(test_db_url: str) -> None:
    engine = create_engine(test_db_url, future=True)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {
        "alembic_version",
        "listings_raw",
        "auctions_raw",
        "parcels",
        "market_metrics_daily",
        "feature_vectors",
        "sync_runs",
        "opportunities",
        "risk_flags",
        "feedback",
        "digests",
        "config_kv",
        "provider_run_events",
    }
    assert expected.issubset(tables)
    engine.dispose()


def test_app_boots_after_migration_without_create_all(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "boot_test.db"
    monkeypatch.setenv("LANDORAMA_DB_PATH", str(db_path))
    monkeypatch.setenv("LANDORAMA_MOCK_MODE", "true")
    get_settings.cache_clear()

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    get_settings.cache_clear()

    app = create_app(enable_scheduler=False, bootstrap_pipeline=False, enable_startup_tasks=True)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
