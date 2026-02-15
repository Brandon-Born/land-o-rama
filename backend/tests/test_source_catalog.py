from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.providers.source_catalog import load_source_catalog, load_source_catalog_with_fallback


def test_source_catalog_loads_expected_counties() -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "county_sources.yaml"
    entries = load_source_catalog(path)
    counties = {entry.county for entry in entries}
    assert {"Hunt", "Collin", "Delta", "Fannin", "Hopkins", "Rains"}.issubset(counties)
    assert all(entry.sources for entry in entries)
    hunt = next(entry for entry in entries if entry.county == "Hunt")
    assert any(source.parser_template_key == "lgbs_property_sales_v1" for source in hunt.sources)


def test_source_catalog_invalid_parser_key_fails(tmp_path) -> None:
    path = tmp_path / "invalid_catalog.yaml"
    path.write_text(
        """
version: 1
counties:
  - label: Test County, TX
    county: Test
    state: TX
    sources:
      - url: https://example.test/source.csv
        parser_template_key: bad_key
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid parser_template_key"):
        load_source_catalog(path)


def test_source_catalog_missing_file_falls_back_to_legacy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LANDORAMA_SOURCE_CATALOG_PATH", str(tmp_path / "missing.yaml"))
    monkeypatch.setenv("LANDORAMA_SCRAPER_HUNT_SOURCE_URLS", "https://example.test/hunt.csv")
    monkeypatch.setenv("LANDORAMA_SCRAPER_ALLOWED_HOSTS", "example.test")
    get_settings.cache_clear()
    runtime = get_settings()
    loaded = load_source_catalog_with_fallback(runtime)
    assert loaded.warning is not None
    assert len(loaded.entries) == 1
    assert loaded.entries[0].county == "Hunt"
    assert loaded.entries[0].sources[0].source_url == "https://example.test/hunt.csv"
    assert loaded.entries[0].sources[0].parser_template_key == "csv_taxsale_v1"
    get_settings.cache_clear()


def test_source_catalog_legacy_fallback_infers_json_template(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LANDORAMA_SOURCE_CATALOG_PATH", str(tmp_path / "missing.yaml"))
    monkeypatch.setenv("LANDORAMA_SCRAPER_HUNT_SOURCE_URLS", "https://example.test/hunt.json")
    monkeypatch.setenv("LANDORAMA_SCRAPER_ALLOWED_HOSTS", "example.test")
    get_settings.cache_clear()
    runtime = get_settings()
    loaded = load_source_catalog_with_fallback(runtime)
    assert loaded.entries[0].sources[0].parser_template_key == "lgbs_property_sales_v1"
    get_settings.cache_clear()
