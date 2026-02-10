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
    rapidapi_provider_slug: str = "land-listings"
    rapidapi_metrics_slug: str = "county-market-metrics"
    auction_source_mode: str = "mock"
    auction_csv_dir: str = "/Users/bborn/land-o-rama/data/auction_feeds"
    auction_csv_glob: str = "*.csv"
    auction_max_file_age_days: int = 14
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

    @property
    def sqlite_url(self) -> str:
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
