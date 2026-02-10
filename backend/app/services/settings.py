from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConfigKV
from app.schemas.api import SettingsResponse, SettingsUpdate

DEFAULTS = {
    "state": get_settings().default_state,
    "refresh_time": get_settings().refresh_time,
    "mock_mode": "true" if get_settings().mock_mode else "false",
    "disclaimers_enabled": "true",
}


def ensure_default_settings(db: Session) -> None:
    for key, value in DEFAULTS.items():
        existing = db.get(ConfigKV, key)
        if not existing:
            db.add(ConfigKV(key=key, value=value))
    db.commit()


def read_settings(db: Session) -> SettingsResponse:
    ensure_default_settings(db)
    values: dict[str, str] = {}
    for key in DEFAULTS:
        record = db.get(ConfigKV, key)
        if record:
            values[key] = record.value
    return SettingsResponse(
        state=values.get("state", DEFAULTS["state"]),
        refresh_time=values.get("refresh_time", DEFAULTS["refresh_time"]),
        mock_mode=values.get("mock_mode", DEFAULTS["mock_mode"]) == "true",
        disclaimers_enabled=values.get("disclaimers_enabled", "true") == "true",
    )


def update_settings(db: Session, payload: SettingsUpdate) -> SettingsResponse:
    ensure_default_settings(db)
    if payload.refresh_time is not None:
        _upsert(db, "refresh_time", payload.refresh_time)
    if payload.mock_mode is not None:
        _upsert(db, "mock_mode", "true" if payload.mock_mode else "false")
    db.commit()
    return read_settings(db)


def _upsert(db: Session, key: str, value: str) -> None:
    existing = db.get(ConfigKV, key)
    if existing:
        existing.value = value
        return
    db.add(ConfigKV(key=key, value=value))
