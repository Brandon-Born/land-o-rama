from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.providers.source_catalog import CountySourceBinding, load_source_catalog_with_fallback


@dataclass(slots=True)
class CountyRegistryEntry:
    label: str
    county: str
    state: str
    parser_key: str
    enabled: bool
    sources: list[CountySourceBinding]


def build_county_registry(settings: Settings) -> list[CountyRegistryEntry]:
    registry, _warning = build_county_registry_with_warning(settings)
    return registry


def build_county_registry_with_warning(settings: Settings) -> tuple[list[CountyRegistryEntry], str | None]:
    loaded = load_source_catalog_with_fallback(settings)
    target_labels = {item.strip().lower() for item in settings.scraper_target_county_list}
    registry: list[CountyRegistryEntry] = []
    for entry in loaded.entries:
        label = entry.label
        county = entry.county
        registry.append(
            CountyRegistryEntry(
                label=label,
                county=county,
                state=entry.state,
                parser_key="template_mesh_v1",
                enabled=(label.lower() in target_labels) or (county.lower() in target_labels),
                sources=entry.sources,
            )
        )
    return registry, loaded.warning
