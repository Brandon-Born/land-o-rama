from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
