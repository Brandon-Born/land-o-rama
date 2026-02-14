from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models import ConfigKV, ProviderRunEvent, ScrapeArtifact
from app.services.pipeline import run_daily_pipeline

ValidationMode = Literal["fixture", "live"]

DEFAULT_REPORT_DIR = Path("/Users/bborn/projects/land-o-rama/data/validation")


@dataclass(slots=True)
class ValidationEffectiveSettings:
    mock_mode: bool
    auction_source_mode: str
    scraper_target_counties: list[str]
    scraper_mode: str
    price_cap: float


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


def validate_hunt_pull(
    *,
    mode: ValidationMode,
    strict: bool = False,
    output_path: Path | None = None,
    session_factory: Callable[[], Session] | None = None,
    env_file: Path | None = None,
    fixture_path: Path | None = None,
) -> HuntPullValidationReport:
    if env_file is not None and env_file.exists():
        _load_env_file(env_file)

    if mode == "fixture":
        fixture = fixture_path or _default_fixture_path()
        fixture_download_dir = fixture.parent / "scraper_downloads"
        os.environ.setdefault("LANDORAMA_DB_PATH", "/Users/bborn/projects/land-o-rama/data/landorama.db")
        os.environ["LANDORAMA_MOCK_MODE"] = "false"
        os.environ["LANDORAMA_AUCTION_SOURCE_MODE"] = "scraper"
        os.environ["LANDORAMA_SCRAPER_TARGET_COUNTIES"] = "hunt"
        os.environ["LANDORAMA_SCRAPER_HUNT_SOURCE_URLS"] = str(fixture)
        os.environ["LANDORAMA_SCRAPER_DOWNLOAD_DIR"] = str(fixture_download_dir)
        os.environ["LANDORAMA_SCRAPER_ALLOWED_HOSTS"] = ""
        os.environ["LANDORAMA_SCRAPER_REQUEST_INTERVAL_MS"] = "0"
        os.environ.setdefault("LANDORAMA_SCRAPER_MODE", "download_first")

    get_settings.cache_clear()
    runtime = get_settings()
    checked_urls = list(runtime.scraper_hunt_source_url_list)

    failure_reasons: list[str] = []
    warning_samples: list[str] = []
    run_id: str | None = None
    run_status: str | None = None
    scraper_status: str | None = None
    hunt_artifact_count = 0
    hunt_records_found = 0
    hunt_records_accepted = 0
    hunt_records_rejected = 0

    if runtime.mock_mode:
        failure_reasons.append("Preflight failed: LANDORAMA_MOCK_MODE must be false.")
    if runtime.auction_source_mode.strip().lower() != "scraper":
        failure_reasons.append("Preflight failed: LANDORAMA_AUCTION_SOURCE_MODE must be scraper.")
    target_counties = {value.strip().lower() for value in runtime.scraper_target_county_list}
    if "hunt" not in target_counties and "hunt county" not in target_counties and "hunt county, tx" not in target_counties:
        failure_reasons.append("Preflight failed: scraper target counties must include Hunt.")
    if not checked_urls:
        failure_reasons.append("Preflight failed: LANDORAMA_SCRAPER_HUNT_SOURCE_URLS must be configured.")

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
                primary_scraper_event = next((event for event in scraper_events if event.provider == "county_auction_scraper"), None)
                if primary_scraper_event is not None:
                    scraper_status = primary_scraper_event.status
                elif scraper_events:
                    scraper_status = scraper_events[0].status

                for event in scraper_events:
                    if event.error_summary and len(warning_samples) < 3:
                        warning_samples.append(event.error_summary)

                hunt_artifacts = db.scalars(
                    select(ScrapeArtifact).where(
                        ScrapeArtifact.run_id == run.id,
                        ScrapeArtifact.county == "Hunt",
                    )
                ).all()
                hunt_artifact_count = len(hunt_artifacts)
                hunt_records_found = sum(artifact.records_found for artifact in hunt_artifacts)
                hunt_records_accepted = sum(artifact.records_accepted for artifact in hunt_artifacts)
                hunt_records_rejected = sum(artifact.records_rejected for artifact in hunt_artifacts)

                if run.status == "failed":
                    failure_reasons.append("Pipeline run failed.")
                if any(event.provider == "county_auction_scraper" and event.status == "failed" for event in scraper_events):
                    failure_reasons.append("County auction scraper reported a failed provider event.")
                if hunt_artifact_count == 0:
                    failure_reasons.append("No Hunt scrape artifacts were persisted for the run.")
                if hunt_records_accepted < 1:
                    failure_reasons.append("No accepted Hunt auction records were ingested.")
                if strict and warning_samples:
                    failure_reasons.append("Strict mode failed because scraper warnings were present.")
        finally:
            if engine is not None:
                engine.dispose()

    report = HuntPullValidationReport(
        validation_id=str(uuid.uuid4()),
        validated_at=datetime.now(UTC).isoformat(),
        mode=mode,
        passed=len(failure_reasons) == 0,
        failure_reasons=failure_reasons,
        run_id=run_id,
        run_status=run_status,
        scraper_provider_status=scraper_status,
        hunt_artifact_count=hunt_artifact_count,
        hunt_records_found=hunt_records_found,
        hunt_records_accepted=hunt_records_accepted,
        hunt_records_rejected=hunt_records_rejected,
        source_urls_checked=checked_urls,
        warning_samples=warning_samples,
        effective_settings=ValidationEffectiveSettings(
            mock_mode=runtime.mock_mode,
            auction_source_mode=runtime.auction_source_mode,
            scraper_target_counties=runtime.scraper_target_county_list,
            scraper_mode=runtime.scraper_mode,
            price_cap=runtime.price_cap,
        ),
    )

    report_path = output_path or _default_output_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report


def _load_env_file(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key] = value


def _default_output_path() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_REPORT_DIR / f"hunt_pull_{stamp}.json"


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "hunt" / "hunt_pull_valid_sample.csv"


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(alembic_cfg, "head")
