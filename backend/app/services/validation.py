from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Literal

from sqlalchemy import create_engine, desc, func, select
from sqlalchemy.orm import Session, sessionmaker
import yaml

from app.core.config import get_settings
from app.models import ConfigKV, ProviderRunEvent, ScrapeArtifact, SyncRun
from app.providers.county_registry import build_county_registry
from app.services.pipeline import run_daily_pipeline

ValidationMode = Literal["fixture", "live"]

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
DATA_ROOT = REPO_ROOT / "data"
DEFAULT_REPORT_DIR = REPO_ROOT / "data" / "validation"


@dataclass(slots=True)
class ValidationEffectiveSettings:
    mock_mode: bool
    auction_source_mode: str
    scraper_target_counties: list[str]
    scraper_mode: str
    price_cap: float
    ingestion_price_cap: float
    live_yield_fail_streak: int
    live_yield_lookback_runs: int


@dataclass(slots=True)
class CountyValidationStatus:
    county: str
    sources_attempted: int
    sources_successful: int
    records_found: int
    records_accepted: int
    records_rejected: int
    provider_status: str
    status: str
    availability_status: str
    yield_status: str
    yield_zero_accepted_streak: int
    min_price: float | None
    median_price: float | None
    max_price: float | None


@dataclass(slots=True)
class CountyPullValidationReport:
    validation_id: str
    validated_at: str
    mode: ValidationMode
    passed: bool
    failure_reasons: list[str]
    run_id: str | None
    run_status: str | None
    scraper_provider_status: str | None
    counties: list[CountyValidationStatus]
    source_urls_checked: list[str]
    warning_samples: list[str]
    effective_settings: ValidationEffectiveSettings

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["effective_settings"] = asdict(self.effective_settings)
        return payload


@dataclass(slots=True)
class HuntPullValidationReport:
    validation_id: str
    validated_at: str
    mode: ValidationMode
    passed: bool
    failure_reasons: list[str]
    run_id: str | None
    run_status: str | None
    scraper_provider_status: str | None
    hunt_artifact_count: int
    hunt_records_found: int
    hunt_records_accepted: int
    hunt_records_rejected: int
    source_urls_checked: list[str]
    warning_samples: list[str]
    effective_settings: ValidationEffectiveSettings

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["effective_settings"] = asdict(self.effective_settings)
        return payload


def validate_county_pull(
    *,
    mode: ValidationMode,
    counties: list[str] | None = None,
    strict: bool = False,
    output_path: Path | None = None,
    session_factory: Callable[[], Session] | None = None,
    env_file: Path | None = None,
    fixture_path: Path | None = None,
) -> CountyPullValidationReport:
    env_overrides: dict[str, str] = {}
    if env_file is not None and env_file.exists():
        env_overrides.update(_load_env_file(env_file))

    fixture_catalog_path: Path | None = None
    selected_counties = [item.strip() for item in (counties or []) if item.strip()]
    if mode == "fixture":
        fixture = fixture_path or _default_fixture_path()
        fixture_download_dir = DEFAULT_REPORT_DIR / "scraper_downloads"
        selected_counties = selected_counties or ["hunt"]
        fixture_catalog_path = _write_fixture_catalog(selected_counties, fixture)
        env_overrides.setdefault("LANDORAMA_DB_PATH", str(DATA_ROOT / "landorama.db"))
        env_overrides["LANDORAMA_MOCK_MODE"] = "false"
        env_overrides["LANDORAMA_AUCTION_SOURCE_MODE"] = "scraper"
        env_overrides["LANDORAMA_SCRAPER_TARGET_COUNTIES"] = ",".join(selected_counties)
        env_overrides["LANDORAMA_SOURCE_CATALOG_PATH"] = str(fixture_catalog_path)
        env_overrides["LANDORAMA_SCRAPER_DOWNLOAD_DIR"] = str(fixture_download_dir)
        env_overrides["LANDORAMA_SCRAPER_ALLOWED_HOSTS"] = ""
        env_overrides["LANDORAMA_SCRAPER_REQUEST_INTERVAL_MS"] = "0"
        env_overrides.setdefault("LANDORAMA_SCRAPER_MODE", "download_first")
    elif selected_counties:
        env_overrides["LANDORAMA_SCRAPER_TARGET_COUNTIES"] = ",".join(selected_counties)

    try:
        with _temporary_env(env_overrides):
            get_settings.cache_clear()
            runtime = get_settings()
            registry = [entry for entry in build_county_registry(runtime) if entry.enabled]
            source_urls_checked = [source.source_url for entry in registry for source in entry.sources]
            live_yield_fail_streak = max(1, int(os.getenv("LANDORAMA_LIVE_YIELD_FAIL_STREAK", "3")))
            live_yield_lookback_runs = max(
                live_yield_fail_streak,
                int(os.getenv("LANDORAMA_LIVE_YIELD_LOOKBACK_RUNS", "7")),
            )

            failure_reasons: list[str] = []
            warning_samples: list[str] = []
            run_id: str | None = None
            run_status: str | None = None
            scraper_status: str | None = None
            county_statuses: list[CountyValidationStatus] = []

            if runtime.mock_mode:
                failure_reasons.append("Preflight failed: LANDORAMA_MOCK_MODE must be false.")
            if runtime.auction_source_mode.strip().lower() != "scraper":
                failure_reasons.append("Preflight failed: LANDORAMA_AUCTION_SOURCE_MODE must be scraper.")
            if not registry:
                failure_reasons.append("Preflight failed: no enabled counties were found for validation.")

            if not failure_reasons:
                engine = None
                factory = session_factory
                if factory is None:
                    _run_migrations()
                    engine = create_engine(
                        runtime.sqlite_url,
                        connect_args={"check_same_thread": False},
                        future=True,
                    )
                    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
                try:
                    with factory() as db:
                        if mode == "fixture":
                            db_mock_mode = db.get(ConfigKV, "mock_mode")
                            if db_mock_mode is None:
                                db.add(ConfigKV(key="mock_mode", value="false"))
                            else:
                                db_mock_mode.value = "false"
                            db.commit()

                        run = run_daily_pipeline(db)
                        run_id = run.id
                        run_status = run.status

                        events = db.scalars(select(ProviderRunEvent).where(ProviderRunEvent.run_id == run.id)).all()
                        scraper_events = [event for event in events if event.provider in {"county_auction_scraper", "scraper_no_new_data"}]
                        primary_scraper_event = next(
                            (event for event in scraper_events if event.provider == "county_auction_scraper"), None
                        )
                        if primary_scraper_event is not None:
                            scraper_status = primary_scraper_event.status
                        elif scraper_events:
                            scraper_status = scraper_events[0].status

                        for event in scraper_events:
                            if event.error_summary and len(warning_samples) < 5:
                                warning_samples.append(event.error_summary)

                        live_yield_failures: list[str] = []
                        for entry in registry:
                            artifacts = db.scalars(
                                select(ScrapeArtifact).where(
                                    ScrapeArtifact.run_id == run.id,
                                    ScrapeArtifact.county == entry.county,
                                )
                            ).all()
                            found = sum(artifact.records_found for artifact in artifacts)
                            accepted = sum(artifact.records_accepted for artifact in artifacts)
                            rejected = sum(artifact.records_rejected for artifact in artifacts)
                            mins = [artifact.price_min for artifact in artifacts if artifact.price_min is not None]
                            medians = [artifact.price_median for artifact in artifacts if artifact.price_median is not None]
                            maxes = [artifact.price_max for artifact in artifacts if artifact.price_max is not None]
                            source_attempted = len(entry.sources)
                            source_successful = len(artifacts)
                            availability_status = "success"
                            yield_status = "success"
                            yield_zero_accepted_streak = 0
                            if source_attempted > 0 and source_successful == 0:
                                availability_status = "failed"
                            elif mode == "fixture" and accepted < 1:
                                yield_status = "failed"
                            elif mode == "live" and found < 1:
                                availability_status = "failed"
                            elif mode == "live" and accepted < 1:
                                yield_status = "warning"
                                if len(warning_samples) < 5:
                                    warning_samples.append(
                                        f"{entry.county}: parsed rows were found, but none were accepted after filters."
                                    )
                                yield_zero_accepted_streak = _compute_live_zero_accepted_streak(
                                    db,
                                    county=entry.county,
                                    source_urls=[source.source_url for source in entry.sources],
                                    lookback_runs=live_yield_lookback_runs,
                                )
                                if yield_zero_accepted_streak >= live_yield_fail_streak:
                                    yield_status = "failed"
                                    live_yield_failures.append(
                                        (
                                            f"{entry.county}: zero accepted rows persisted for "
                                            f"{yield_zero_accepted_streak} consecutive live runs."
                                        )
                                    )

                            county_status = "success"
                            if availability_status == "failed" or yield_status == "failed":
                                county_status = "failed"
                            elif availability_status == "warning" or yield_status == "warning":
                                county_status = "warning"
                            provider_status = county_status

                            county_statuses.append(
                                CountyValidationStatus(
                                    county=entry.county,
                                    sources_attempted=source_attempted,
                                    sources_successful=source_successful,
                                    records_found=found,
                                    records_accepted=accepted,
                                    records_rejected=rejected,
                                    provider_status=provider_status,
                                    status=county_status,
                                    availability_status=availability_status,
                                    yield_status=yield_status,
                                    yield_zero_accepted_streak=yield_zero_accepted_streak,
                                    min_price=min(mins) if mins else None,
                                    median_price=(sum(medians) / len(medians)) if medians else None,
                                    max_price=max(maxes) if maxes else None,
                                )
                            )

                        if run.status == "failed":
                            failure_reasons.append("Pipeline run failed.")
                        if any(
                            event.provider == "county_auction_scraper" and event.status == "failed"
                            for event in scraper_events
                        ):
                            failure_reasons.append("County auction scraper reported a failed provider event.")
                        failed_counties = [item.county for item in county_statuses if item.status == "failed"]
                        if failed_counties:
                            failure_reasons.append("County validation failed for: " + ", ".join(sorted(failed_counties)))
                        if live_yield_failures:
                            failure_reasons.append(
                                "Live yield gate failed: " + "; ".join(sorted(live_yield_failures))
                            )
                        if mode == "live":
                            passing = [item for item in county_statuses if item.status in {"success", "warning"}]
                            required = min(4, len(county_statuses))
                            if len(passing) < required:
                                failure_reasons.append(
                                    f"Live validation requires {required} passing counties; observed {len(passing)}."
                                )
                        if strict and warning_samples:
                            failure_reasons.append("Strict mode failed because scraper warnings were present.")
                finally:
                    if engine is not None:
                        engine.dispose()

            report = CountyPullValidationReport(
                validation_id=str(uuid.uuid4()),
                validated_at=datetime.now(UTC).isoformat(),
                mode=mode,
                passed=len(failure_reasons) == 0,
                failure_reasons=failure_reasons,
                run_id=run_id,
                run_status=run_status,
                scraper_provider_status=scraper_status,
                counties=county_statuses,
                source_urls_checked=source_urls_checked,
                warning_samples=warning_samples,
                effective_settings=ValidationEffectiveSettings(
                    mock_mode=runtime.mock_mode,
                    auction_source_mode=runtime.auction_source_mode,
                    scraper_target_counties=runtime.scraper_target_county_list,
                    scraper_mode=runtime.scraper_mode,
                    price_cap=runtime.price_cap,
                    ingestion_price_cap=runtime.ingestion_price_cap,
                    live_yield_fail_streak=live_yield_fail_streak,
                    live_yield_lookback_runs=live_yield_lookback_runs,
                ),
            )
            report_path = output_path or _default_output_path(prefix="county_pull")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
            return report
    finally:
        get_settings.cache_clear()
        if fixture_catalog_path is not None and fixture_catalog_path.exists():
            fixture_catalog_path.unlink(missing_ok=True)


def validate_hunt_pull(
    *,
    mode: ValidationMode,
    strict: bool = False,
    output_path: Path | None = None,
    session_factory: Callable[[], Session] | None = None,
    env_file: Path | None = None,
    fixture_path: Path | None = None,
) -> HuntPullValidationReport:
    report = validate_county_pull(
        mode=mode,
        counties=["hunt"],
        strict=strict,
        output_path=output_path,
        session_factory=session_factory,
        env_file=env_file,
        fixture_path=fixture_path,
    )
    hunt = next((item for item in report.counties if item.county.lower() == "hunt"), None)
    failure_reasons = list(report.failure_reasons)
    if (
        hunt is not None
        and hunt.records_accepted < 1
        and report.mode == "fixture"
        and "No accepted Hunt auction records were ingested." not in failure_reasons
    ):
        failure_reasons.append("No accepted Hunt auction records were ingested.")
    return HuntPullValidationReport(
        validation_id=report.validation_id,
        validated_at=report.validated_at,
        mode=report.mode,
        passed=report.passed,
        failure_reasons=failure_reasons,
        run_id=report.run_id,
        run_status=report.run_status,
        scraper_provider_status=report.scraper_provider_status,
        hunt_artifact_count=hunt.sources_successful if hunt else 0,
        hunt_records_found=hunt.records_found if hunt else 0,
        hunt_records_accepted=hunt.records_accepted if hunt else 0,
        hunt_records_rejected=hunt.records_rejected if hunt else 0,
        source_urls_checked=report.source_urls_checked,
        warning_samples=report.warning_samples,
        effective_settings=report.effective_settings,
    )


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


@contextmanager
def _temporary_env(overrides: dict[str, str]):
    originals: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    for key, value in overrides.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, original in originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def _default_output_path(*, prefix: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_REPORT_DIR / f"{prefix}_{stamp}.json"


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "hunt" / "hunt_pull_valid_sample.csv"


def _write_fixture_catalog(counties: list[str], fixture_path: Path) -> Path:
    county_entries = []
    for county_token in counties:
        raw = county_token.strip()
        lowered = raw.lower()
        county = raw
        if "county" in lowered:
            county = raw[: lowered.index("county")].strip()
        county = county.split(",")[0].strip().title() or raw.title()
        county_entries.append(
            {
                "label": f"{county} County, TX",
                "county": county,
                "state": "TX",
                "sources": [
                    {
                        "url": str(fixture_path),
                        "parser_template_key": "csv_taxsale_v1",
                        "allowed_hosts": [],
                        "priority": 10,
                        "source_name": f"{county} Fixture Source",
                    }
                ],
            }
        )
    payload = {"version": 1, "counties": county_entries}
    with NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False) as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
        return Path(handle.name)


def _compute_live_zero_accepted_streak(
    db: Session,
    *,
    county: str,
    source_urls: list[str],
    lookback_runs: int,
) -> int:
    normalized_sources = [url for url in source_urls if url]
    if lookback_runs <= 0 or not normalized_sources:
        return 0

    rows = db.execute(
        select(
            SyncRun.id,
            func.sum(ScrapeArtifact.records_found).label("records_found"),
            func.sum(ScrapeArtifact.records_accepted).label("records_accepted"),
        )
        .join(ScrapeArtifact, ScrapeArtifact.run_id == SyncRun.id)
        .where(
            ScrapeArtifact.county == county,
            ScrapeArtifact.source_url.in_(normalized_sources),
            SyncRun.status.in_(["success", "degraded"]),
        )
        .group_by(SyncRun.id, SyncRun.started_at)
        .order_by(desc(SyncRun.started_at))
        .limit(lookback_runs)
    ).all()

    streak = 0
    for _, records_found, records_accepted in rows:
        found = int(records_found or 0)
        accepted = int(records_accepted or 0)
        if found > 0 and accepted < 1:
            streak += 1
        else:
            break
    return streak


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(alembic_cfg, "head")
