from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(slots=True)
class CountyRegistryEntry:
    label: str
    county: str
    state: str
    parser_key: str
    enabled: bool


def build_county_registry(settings: Settings) -> list[CountyRegistryEntry]:
    target_labels = {item.strip().lower() for item in settings.scraper_target_county_list}
    supported = [
        ("Hunt County, TX", "Hunt", "TX", "hunt_download_first"),
        ("Collin County, TX", "Collin", "TX", "county_stub_pending"),
        ("Delta County, TX", "Delta", "TX", "county_stub_pending"),
    ]
    registry: list[CountyRegistryEntry] = []
    for label, county, state, parser_key in supported:
        registry.append(
            CountyRegistryEntry(
                label=label,
                county=county,
                state=state,
                parser_key=parser_key,
                enabled=(label.lower() in target_labels) or (county.lower() in target_labels),
            )
        )
    return registry
