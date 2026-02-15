from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
DATA_ROOT = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANDORAMA_", extra="ignore")

    app_name: str = "Land-O-Rama API"
    db_path: str = str(DATA_ROOT / "landorama.db")
    cors_origins: str = "http://localhost:5173"
    default_state: str = "TX"
    refresh_time: str = "08:00"
    personalization_retrain_time: str = "02:30"
    mock_mode: bool = True
    price_cap: float = 5000.0
    ingestion_price_cap: float = 15000.0
    auction_source_mode: str = "scraper"
    auction_csv_dir: str = str(DATA_ROOT / "auction_feeds")
    auction_csv_glob: str = "*.csv"
    auction_max_file_age_days: int = 14
    scraper_mode: str = "download_first"
    scraper_target_counties: str = "hunt"
    source_catalog_path: str = str(BACKEND_ROOT / "config" / "county_sources.yaml")
    scraper_hunt_source_urls: str = ""
    scraper_download_dir: str = str(DATA_ROOT / "scraper_downloads")
    scraper_allowed_hosts: str = ""
    scraper_request_interval_ms: int = 1000
    regrid_api_key: str | None = None
    provider_timeout_seconds: float = 12.0
    provider_max_retries: int = 2
    market_metrics_cache_lookback_days: int = 30
    personalization_threshold: int = 50
    personalization_blend_weight: float = 0.15
    personalization_model_path: str = str(DATA_ROOT / "models" / "personalization_v1.joblib")

    @field_validator("default_state")
    @classmethod
    def _normalize_state(cls, value: str) -> str:
        return value.strip().upper()

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
