from __future__ import annotations

from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConfigKV, Feedback, ModelTrainingRun, ProviderRunEvent, ScrapeArtifact
from app.providers.county_registry import build_county_registry
from app.schemas.api import ProviderEventStatus, ScraperCountyCoverage, SettingsResponse, SettingsUpdate


def _defaults() -> dict[str, str]:
    runtime = get_settings()
    return {
        "state": runtime.default_state,
        "refresh_time": runtime.refresh_time,
        "mock_mode": "true" if runtime.mock_mode else "false",
        "disclaimers_enabled": "true",
    }


def ensure_default_settings(db: Session) -> None:
    defaults = _defaults()
    for key, value in defaults.items():
        existing = db.get(ConfigKV, key)
        if not existing:
            db.add(ConfigKV(key=key, value=value))
    db.commit()


def read_settings(db: Session) -> SettingsResponse:
    ensure_default_settings(db)
    runtime = get_settings()
    defaults = _defaults()
    values: dict[str, str] = {}
    for key in defaults:
        record = db.get(ConfigKV, key)
        if record:
            values[key] = record.value
    label_count = db.scalar(
        select(func.count()).select_from(Feedback).where(Feedback.vote.in_(["up", "down"]))
    ) or 0
    latest_training = db.scalar(
        select(ModelTrainingRun).where(ModelTrainingRun.status == "success").order_by(ModelTrainingRun.trained_at.desc()).limit(1)
    )
    latest_scrape_artifact = db.scalar(select(ScrapeArtifact).order_by(ScrapeArtifact.created_at.desc()).limit(1))
    latest_success_scrape = db.scalar(
        select(ScrapeArtifact)
        .where(ScrapeArtifact.records_accepted > 0)
        .order_by(ScrapeArtifact.fetched_at.desc())
        .limit(1)
    )
    scraper_parse_error_count = 0
    scraper_last_records_accepted = 0
    if latest_scrape_artifact is not None:
        scraper_parse_error_count = (
            db.scalar(
                select(func.coalesce(func.sum(ScrapeArtifact.records_rejected), 0)).where(
                    ScrapeArtifact.run_id == latest_scrape_artifact.run_id
                )
            )
            or 0
        )
        scraper_last_records_accepted = (
            db.scalar(
                select(func.coalesce(func.sum(ScrapeArtifact.records_accepted), 0)).where(
                    ScrapeArtifact.run_id == latest_scrape_artifact.run_id
                )
            )
            or 0
        )
    provider_health = _provider_health(db)
    county_registry = build_county_registry(runtime)
    enabled_counties = sorted({entry.county for entry in county_registry if entry.enabled})
    county_coverage = _scraper_county_coverage(db, counties=enabled_counties)
    county_failures = sum(1 for item in county_coverage if item.status == "failed")
    return SettingsResponse(
        state=values.get("state", defaults["state"]),
        refresh_time=values.get("refresh_time", defaults["refresh_time"]),
        mock_mode=values.get("mock_mode", defaults["mock_mode"]) == "true",
        disclaimers_enabled=values.get("disclaimers_enabled", "true") == "true",
        regrid_configured=bool(runtime.regrid_api_key),
        price_cap=runtime.price_cap,
        auction_source_mode=runtime.auction_source_mode,
        auction_csv_dir=runtime.auction_csv_dir,
        auction_csv_glob=runtime.auction_csv_glob,
        auction_max_file_age_days=runtime.auction_max_file_age_days,
        provider_timeout_seconds=runtime.provider_timeout_seconds,
        provider_max_retries=runtime.provider_max_retries,
        market_metrics_cache_lookback_days=runtime.market_metrics_cache_lookback_days,
        scraper_primary_source="county_auction_scraper",
        scraper_mode=runtime.scraper_mode,
        scraper_target_counties=runtime.scraper_target_county_list,
        scraper_last_success_at=latest_success_scrape.fetched_at if latest_success_scrape else None,
        scraper_last_success_county=latest_success_scrape.county if latest_success_scrape else None,
        scraper_parse_error_count=int(scraper_parse_error_count),
        scraper_last_records_accepted=int(scraper_last_records_accepted),
        scraper_enabled_counties=enabled_counties,
        scraper_county_coverage=county_coverage,
        scraper_county_failures=county_failures,
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


def _scraper_county_coverage(db: Session, *, counties: list[str]) -> list[ScraperCountyCoverage]:
    coverage: list[ScraperCountyCoverage] = []
    for county in counties:
        latest_artifact = db.scalar(
            select(ScrapeArtifact)
            .where(ScrapeArtifact.county == county)
            .order_by(ScrapeArtifact.fetched_at.desc())
            .limit(1)
        )
        last_success_at = db.scalar(
            select(ScrapeArtifact.fetched_at)
            .where(ScrapeArtifact.county == county, ScrapeArtifact.records_accepted > 0)
            .order_by(ScrapeArtifact.fetched_at.desc())
            .limit(1)
        )
        if latest_artifact is None:
            coverage.append(
                ScraperCountyCoverage(
                    county=county,
                    last_success_at=last_success_at,
                    status="failed",
                )
            )
            continue

        records_found = (
            db.scalar(
                select(func.coalesce(func.sum(ScrapeArtifact.records_found), 0)).where(
                    ScrapeArtifact.run_id == latest_artifact.run_id,
                    ScrapeArtifact.county == county,
                )
            )
            or 0
        )
        records_accepted = (
            db.scalar(
                select(func.coalesce(func.sum(ScrapeArtifact.records_accepted), 0)).where(
                    ScrapeArtifact.run_id == latest_artifact.run_id,
                    ScrapeArtifact.county == county,
                )
            )
            or 0
        )
        records_rejected = (
            db.scalar(
                select(func.coalesce(func.sum(ScrapeArtifact.records_rejected), 0)).where(
                    ScrapeArtifact.run_id == latest_artifact.run_id,
                    ScrapeArtifact.county == county,
                )
            )
            or 0
        )
        min_price = db.scalar(
            select(func.min(ScrapeArtifact.price_min)).where(
                ScrapeArtifact.run_id == latest_artifact.run_id,
                ScrapeArtifact.county == county,
                ScrapeArtifact.price_min.is_not(None),
            )
        )
        max_price = db.scalar(
            select(func.max(ScrapeArtifact.price_max)).where(
                ScrapeArtifact.run_id == latest_artifact.run_id,
                ScrapeArtifact.county == county,
                ScrapeArtifact.price_max.is_not(None),
            )
        )
        medians = db.scalars(
            select(ScrapeArtifact.price_median).where(
                ScrapeArtifact.run_id == latest_artifact.run_id,
                ScrapeArtifact.county == county,
                ScrapeArtifact.price_median.is_not(None),
            )
        ).all()
        median_price = float(median(medians)) if medians else None
        if records_accepted > 0:
            status = "success"
        elif records_found > 0:
            status = "warning"
        else:
            status = "failed"
        coverage.append(
            ScraperCountyCoverage(
                county=county,
                last_success_at=last_success_at,
                records_found=int(records_found),
                records_accepted=int(records_accepted),
                records_rejected=int(records_rejected),
                min_price=float(min_price) if min_price is not None else None,
                median_price=median_price,
                max_price=float(max_price) if max_price is not None else None,
                status=status,
            )
        )
    return coverage
