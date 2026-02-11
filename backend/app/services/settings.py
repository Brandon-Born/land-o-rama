from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConfigKV, Feedback, ModelTrainingRun, ProviderRunEvent
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
    label_count = db.scalar(
        select(func.count()).select_from(Feedback).where(Feedback.vote.in_(["up", "down"]))
    ) or 0
    latest_training = db.scalar(
        select(ModelTrainingRun).where(ModelTrainingRun.status == "success").order_by(ModelTrainingRun.trained_at.desc()).limit(1)
    )
    provider_health = _provider_health(db)
    return SettingsResponse(
        state=values.get("state", DEFAULTS["state"]),
        refresh_time=values.get("refresh_time", DEFAULTS["refresh_time"]),
        mock_mode=values.get("mock_mode", DEFAULTS["mock_mode"]) == "true",
        disclaimers_enabled=values.get("disclaimers_enabled", "true") == "true",
        rapidapi_configured=bool(runtime.rapidapi_key and runtime.rapidapi_host),
        regrid_configured=bool(runtime.regrid_api_key),
        rapidapi_provider_slug=runtime.rapidapi_provider_slug,
        rapidapi_metrics_slug=runtime.rapidapi_metrics_slug,
        listing_locations_count=len(runtime.listing_location_list),
        listing_page_limit=runtime.listing_page_limit,
        listing_pages_per_location=runtime.listing_pages_per_location,
        listing_sort=runtime.listing_sort,
        listing_price_max=runtime.listing_price_max,
        auction_source_mode=runtime.auction_source_mode,
        auction_csv_dir=runtime.auction_csv_dir,
        auction_csv_glob=runtime.auction_csv_glob,
        auction_max_file_age_days=runtime.auction_max_file_age_days,
        provider_timeout_seconds=runtime.provider_timeout_seconds,
        provider_max_retries=runtime.provider_max_retries,
        market_metrics_cache_lookback_days=runtime.market_metrics_cache_lookback_days,
        personalization_ready=bool(latest_training and label_count >= runtime.personalization_threshold),
        feedback_labels_count=label_count,
        personalization_threshold=runtime.personalization_threshold,
        personalization_blend_weight=runtime.personalization_blend_weight,
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
