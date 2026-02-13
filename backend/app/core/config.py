from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANDORAMA_", extra="ignore")

    app_name: str = "Land-O-Rama API"
    db_path: str = "/Users/bborn/land-o-rama/data/landorama.db"
    cors_origins: str = "http://localhost:5173"
    default_state: str = "TX"
    refresh_time: str = "08:00"
    personalization_retrain_time: str = "02:30"
    mock_mode: bool = True
    rapidapi_key: str | None = None
    rapidapi_host: str | None = None
    rapidapi_provider_slug: str = "for-sale"
    rapidapi_metrics_slug: str = "county-market-metrics"
    listing_locations: str = ""
    listing_page_limit: int = 50
    listing_pages_per_location: int = 2
    listing_sort: str = "relevance"
    listing_price_max: float = 6000.0
    listing_offset_step: int = 50
    auction_source_mode: str = "scraper"
    auction_csv_dir: str = "/Users/bborn/land-o-rama/data/auction_feeds"
    auction_csv_glob: str = "*.csv"
    auction_max_file_age_days: int = 14
    scraper_mode: str = "download_first"
    scraper_target_counties: str = "Hunt County,TX"
    scraper_hunt_source_urls: str = ""
    scraper_download_dir: str = "/Users/bborn/land-o-rama/data/scraper_downloads"
    scraper_allowed_hosts: str = ""
    scraper_request_interval_ms: int = 1000
    regrid_api_key: str | None = None
    provider_timeout_seconds: float = 12.0
    provider_max_retries: int = 2
    market_metrics_cache_lookback_days: int = 30
    personalization_threshold: int = 50
    personalization_blend_weight: float = 0.15
    personalization_model_path: str = "/Users/bborn/land-o-rama/data/models/personalization_v1.joblib"

    @field_validator("default_state")
    @classmethod
    def _normalize_state(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("rapidapi_provider_slug")
    @classmethod
    def _normalize_provider_slug(cls, value: str) -> str:
        return value.strip().strip("/")

    @field_validator("listing_page_limit")
    @classmethod
    def _validate_listing_page_limit(cls, value: int) -> int:
        return min(200, max(1, value))

    @field_validator("listing_pages_per_location")
    @classmethod
    def _validate_listing_pages_per_location(cls, value: int) -> int:
        return min(10, max(1, value))

    @field_validator("listing_offset_step")
    @classmethod
    def _validate_listing_offset_step(cls, value: int) -> int:
        return max(1, value)

    @field_validator("scraper_request_interval_ms")
    @classmethod
    def _validate_scraper_request_interval_ms(cls, value: int) -> int:
        return max(0, value)

    @property
    def sqlite_url(self) -> str:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def listing_location_list(self) -> list[str]:
        return [location.strip() for location in self.listing_locations.split(",") if location.strip()]

    @property
    def scraper_target_county_list(self) -> list[str]:
        return [county.strip() for county in self.scraper_target_counties.split(",") if county.strip()]

    @property
    def scraper_hunt_source_url_list(self) -> list[str]:
        return [url.strip() for url in self.scraper_hunt_source_urls.split(",") if url.strip()]

    @property
    def scraper_allowed_host_list(self) -> list[str]:
        return [host.strip().lower() for host in self.scraper_allowed_hosts.split(",") if host.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
