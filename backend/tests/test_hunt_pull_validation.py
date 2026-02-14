from __future__ import annotations

import json
from pathlib import Path

from app.services.validation import validate_hunt_pull


def _write_csv(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(rows), encoding="utf-8")


def test_hunt_pull_validation_fixture_success(session_factory, tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "hunt_valid.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-1,PK-1,Hunt,TX,1800,0.2,https://example.test/auctions/H-1",
        ],
    )
    output = tmp_path / "validation_report.json"
    monkeypatch.setenv("LANDORAMA_PROVIDER_TIMEOUT_SECONDS", "1")

    report = validate_hunt_pull(
        mode="fixture",
        session_factory=session_factory,
        fixture_path=fixture,
        output_path=output,
    )

    assert report.passed
    assert report.hunt_records_accepted >= 1
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["passed"] is True


def test_hunt_pull_validation_fixture_missing_columns_fails(session_factory, tmp_path) -> None:
    fixture = tmp_path / "hunt_missing_columns.csv"
    _write_csv(
        fixture,
        [
            "auction_id,county,state,price,acreage,source_url",
            "H-1,Hunt,TX,1800,0.2,https://example.test/auctions/H-1",
        ],
    )

    report = validate_hunt_pull(
        mode="fixture",
        session_factory=session_factory,
        fixture_path=fixture,
        output_path=tmp_path / "missing_columns_report.json",
    )

    assert not report.passed
    assert report.hunt_records_accepted == 0
    assert report.hunt_records_rejected >= 1
    assert "No accepted Hunt auction records were ingested." in report.failure_reasons


def test_hunt_pull_validation_fixture_duplicates_accounted(session_factory, tmp_path) -> None:
    fixture = tmp_path / "hunt_duplicates.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-1,PK-1,Hunt,TX,1800,0.2,https://example.test/auctions/H-1",
            "H-1,PK-1,Hunt,TX,1800,0.2,https://example.test/auctions/H-1",
        ],
    )

    report = validate_hunt_pull(
        mode="fixture",
        session_factory=session_factory,
        fixture_path=fixture,
        output_path=tmp_path / "duplicate_report.json",
    )

    assert report.passed
    assert report.hunt_records_accepted == 1
    assert report.hunt_records_rejected >= 1


def test_hunt_pull_validation_fixture_zero_accepted_fails(session_factory, tmp_path) -> None:
    fixture = tmp_path / "hunt_price_cap_fail.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-1,PK-1,Hunt,TX,7000,0.2,https://example.test/auctions/H-1",
        ],
    )

    report = validate_hunt_pull(
        mode="fixture",
        session_factory=session_factory,
        fixture_path=fixture,
        output_path=tmp_path / "zero_accepted_report.json",
    )

    assert not report.passed
    assert report.hunt_records_accepted == 0
    assert "No accepted Hunt auction records were ingested." in report.failure_reasons


def test_hunt_pull_validation_report_written(session_factory, tmp_path) -> None:
    fixture = tmp_path / "hunt_valid_for_report.csv"
    _write_csv(
        fixture,
        [
            "auction_id,parcel_key,county,state,price,acreage,source_url",
            "H-9,PK-9,Hunt,TX,1500,0.25,https://example.test/auctions/H-9",
        ],
    )
    output = tmp_path / "explicit_report_path.json"

    report = validate_hunt_pull(
        mode="fixture",
        session_factory=session_factory,
        fixture_path=fixture,
        output_path=output,
    )

    assert report.run_id is not None
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["validation_id"] == report.validation_id
