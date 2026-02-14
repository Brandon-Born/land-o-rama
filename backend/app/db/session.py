from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_session_local = None
_session_sqlite_url: str | None = None


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()


def get_session_local():
    global _engine, _session_local, _session_sqlite_url
    settings = get_settings()
    sqlite_url = settings.sqlite_url
    if _session_local is None or _session_sqlite_url != sqlite_url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
            future=True,
        )
        _session_local = sessionmaker(bind=_engine, autoflush=False, autocommit=False, class_=Session)
        _session_sqlite_url = sqlite_url
    return _session_local


SessionLocal = get_session_local()


def get_db() -> Iterator[Session]:
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
