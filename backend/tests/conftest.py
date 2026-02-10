from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def test_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_path = tmp_path / "test_landorama.db"
    monkeypatch.setenv("LANDORAMA_DB_PATH", str(db_path))
    monkeypatch.setenv("LANDORAMA_MOCK_MODE", "true")
    monkeypatch.setenv("LANDORAMA_RAPIDAPI_KEY", "")
    monkeypatch.setenv("LANDORAMA_RAPIDAPI_HOST", "")
    monkeypatch.setenv("LANDORAMA_REGRID_API_KEY", "")
    get_settings.cache_clear()

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    return f"sqlite:///{db_path}"


@pytest.fixture()
def session_factory(test_db_url: str) -> sessionmaker[Session]:
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False}, future=True)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def app(session_factory: sessionmaker[Session]):
    test_app = create_app(enable_startup_tasks=False, enable_scheduler=False, bootstrap_pipeline=False)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture()
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
