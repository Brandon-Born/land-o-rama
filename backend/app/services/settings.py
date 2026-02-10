from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConfigKV, ProviderRunEvent
from app.schemas.api import ProviderEventStatus, SettingsResponse, SettingsUpdate

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
    runtime = get_settings()
    values: dict[str, str] = {}
    for key in DEFAULTS:
        record = db.get(ConfigKV, key)
        if record:
            values[key] = record.value
    provider_health = _provider_health(db)
    return SettingsResponse(
        state=values.get("state", DEFAULTS["state"]),
        refresh_time=values.get("refresh_time", DEFAULTS["refresh_time"]),
        mock_mode=values.get("mock_mode", DEFAULTS["mock_mode"]) == "true",
        disclaimers_enabled=values.get("disclaimers_enabled", "true") == "true",
        rapidapi_configured=bool(runtime.rapidapi_key and runtime.rapidapi_host),
        regrid_configured=bool(runtime.regrid_api_key),
        rapidapi_provider_slug=runtime.rapidapi_provider_slug,
        provider_timeout_seconds=runtime.provider_timeout_seconds,
        provider_max_retries=runtime.provider_max_retries,
        provider_health=provider_health,
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


def _provider_health(db: Session) -> list[ProviderEventStatus]:
    latest_by_provider: dict[str, ProviderRunEvent] = {}
    events = (
        db.query(ProviderRunEvent)
        .order_by(ProviderRunEvent.created_at.desc())
        .limit(50)
        .all()
    )
    for event in events:
        if event.provider not in latest_by_provider:
            latest_by_provider[event.provider] = event
    return [
        ProviderEventStatus(
            provider=event.provider,
            status=event.status,
            error_summary=event.error_summary,
            created_at=event.created_at,
        )
        for event in latest_by_provider.values()
    ]
