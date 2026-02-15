from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.config import Settings
from app.providers.parser_registry import (
    ParserTemplateKey,
    infer_parser_template_from_url,
    is_supported_parser_template_key,
)


@dataclass(slots=True)
class CountySourceBinding:
    source_url: str
    parser_template_key: ParserTemplateKey
    allowed_hosts: list[str] = field(default_factory=list)
    priority: int = 100
    source_name: str | None = None


@dataclass(slots=True)
class SourceCatalogEntry:
    label: str
    county: str
    state: str
    sources: list[CountySourceBinding] = field(default_factory=list)


@dataclass(slots=True)
class LoadedSourceCatalog:
    entries: list[SourceCatalogEntry]
    warning: str | None = None


def load_source_catalog(path: Path) -> list[SourceCatalogEntry]:
    if not path.exists():
        raise FileNotFoundError(path)

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    counties = payload.get("counties")
    if not isinstance(counties, list):
        raise ValueError(f"Invalid source catalog structure in {path}: missing 'counties' list.")

    entries: list[SourceCatalogEntry] = []
    for index, raw_entry in enumerate(counties, start=1):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Invalid source catalog entry #{index}: expected object.")
        label = str(raw_entry.get("label", "")).strip()
        county = str(raw_entry.get("county", "")).strip().title()
        state = str(raw_entry.get("state", "")).strip().upper()
        if not label or not county or not state:
            raise ValueError(f"Invalid source catalog entry #{index}: label/county/state are required.")

        raw_sources = raw_entry.get("sources")
        if not isinstance(raw_sources, list) or not raw_sources:
            raise ValueError(f"Invalid source catalog entry '{label}': at least one source is required.")

        sources: list[CountySourceBinding] = []
        for source_index, raw_source in enumerate(raw_sources, start=1):
            if not isinstance(raw_source, dict):
                raise ValueError(f"Invalid source in '{label}' #{source_index}: expected object.")
            source_url = str(raw_source.get("url", "")).strip()
            parser_template_key = str(raw_source.get("parser_template_key", "")).strip()
            if not source_url or not parser_template_key:
                raise ValueError(
                    f"Invalid source in '{label}' #{source_index}: url and parser_template_key are required."
                )
            if not is_supported_parser_template_key(parser_template_key):
                raise ValueError(
                    f"Invalid parser_template_key '{parser_template_key}' in '{label}' #{source_index}."
                )
            raw_allowed_hosts = raw_source.get("allowed_hosts", [])
            if isinstance(raw_allowed_hosts, str):
                raw_allowed_hosts = [raw_allowed_hosts]
            allowed_hosts = [
                str(host).strip().lower()
                for host in list(raw_allowed_hosts)
                if str(host).strip()
            ]
            priority = int(raw_source.get("priority", 100))
            source_name = str(raw_source.get("source_name", "")).strip() or None
            sources.append(
                CountySourceBinding(
                    source_url=source_url,
                    parser_template_key=parser_template_key,
                    allowed_hosts=allowed_hosts,
                    priority=priority,
                    source_name=source_name,
                )
            )
        sources.sort(key=lambda item: item.priority)
        entries.append(
            SourceCatalogEntry(
                label=label,
                county=county,
                state=state,
                sources=sources,
            )
        )
    return entries


def load_source_catalog_with_fallback(settings: Settings) -> LoadedSourceCatalog:
    catalog_path = Path(settings.source_catalog_path)
    if catalog_path.is_file():
        return LoadedSourceCatalog(entries=load_source_catalog(catalog_path), warning=None)

    # Legacy compatibility for one release cycle: preserve the Hunt-only env path.
    legacy_sources = [
        CountySourceBinding(
            source_url=url,
            parser_template_key=infer_parser_template_from_url(url),
            allowed_hosts=settings.scraper_allowed_host_list,
            priority=100,
            source_name="Legacy Hunt Source",
        )
        for url in settings.scraper_hunt_source_url_list
    ]
    entries = [
        SourceCatalogEntry(
            label="Hunt County, TX",
            county="Hunt",
            state="TX",
            sources=legacy_sources,
        )
    ]
    return LoadedSourceCatalog(
        entries=entries,
        warning=(
            f"Using legacy Hunt-only source configuration because source catalog was not found at {catalog_path}."
        ),
    )
