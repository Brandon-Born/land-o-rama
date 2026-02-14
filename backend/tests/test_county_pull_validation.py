from __future__ import annotations

import json
from pathlib import Path

from app.models import ConfigKV
from app.services.settings import ensure_default_settings
from app.services.validation import validate_county_pull


def _write_csv(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(rows), encoding="utf-8")


def test_county_pull_validation_fixture_success(session_factory, tmp_path) -> None:
    fixture = tmp_path / "county_fixture.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-1,PK-1,Hunt,TX,1800,0.2,https://example.test/auctions/H-1",
        ],
    )
    output = tmp_path / "county_fixture_report.json"
    report = validate_county_pull(
        mode="fixture",
        counties=["hunt"],
        session_factory=session_factory,
        fixture_path=fixture,
        output_path=output,
    )
    assert report.passed
    assert report.counties
    assert report.counties[0].records_accepted >= 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["passed"] is True


def test_county_pull_validation_live_warning_pass(session_factory, tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "county_live_filtered.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-9,PK-9,Hunt,TX,7000,0.3,https://example.test/auctions/H-9",
        ],
    )
    monkeypatch.setenv("LANDORAMA_MOCK_MODE", "false")
    monkeypatch.setenv("LANDORAMA_AUCTION_SOURCE_MODE", "scraper")
    monkeypatch.setenv("LANDORAMA_SCRAPER_TARGET_COUNTIES", "hunt")
    monkeypatch.setenv("LANDORAMA_SOURCE_CATALOG_PATH", "")
    monkeypatch.setenv("LANDORAMA_SCRAPER_HUNT_SOURCE_URLS", str(fixture))
    monkeypatch.setenv("LANDORAMA_SCRAPER_ALLOWED_HOSTS", "")
    monkeypatch.setenv("LANDORAMA_SCRAPER_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    monkeypatch.setenv("LANDORAMA_SCRAPER_REQUEST_INTERVAL_MS", "0")
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

    report = validate_county_pull(
        mode="live",
        counties=["hunt"],
        session_factory=session_factory,
        output_path=tmp_path / "county_live_report.json",
    )
    assert report.passed
    assert report.counties[0].records_found >= 1
    assert report.counties[0].records_accepted == 0
    assert report.counties[0].status == "warning"


def test_county_pull_validation_live_strict_fails_on_warning(session_factory, tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "county_live_filtered_strict.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-10,PK-10,Hunt,TX,7100,0.3,https://example.test/auctions/H-10",
        ],
    )
    monkeypatch.setenv("LANDORAMA_MOCK_MODE", "false")
    monkeypatch.setenv("LANDORAMA_AUCTION_SOURCE_MODE", "scraper")
    monkeypatch.setenv("LANDORAMA_SCRAPER_TARGET_COUNTIES", "hunt")
    monkeypatch.setenv("LANDORAMA_SOURCE_CATALOG_PATH", "")
    monkeypatch.setenv("LANDORAMA_SCRAPER_HUNT_SOURCE_URLS", str(fixture))
    monkeypatch.setenv("LANDORAMA_SCRAPER_ALLOWED_HOSTS", "")
    monkeypatch.setenv("LANDORAMA_SCRAPER_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    monkeypatch.setenv("LANDORAMA_SCRAPER_REQUEST_INTERVAL_MS", "0")
    with session_factory() as db:
        ensure_default_settings(db)
        db.get(ConfigKV, "mock_mode").value = "false"
        db.commit()

    report = validate_county_pull(
        mode="live",
        counties=["hunt"],
        strict=True,
        session_factory=session_factory,
        output_path=tmp_path / "county_live_strict_report.json",
    )
    assert not report.passed
    assert "Strict mode failed because scraper warnings were present." in report.failure_reasons
