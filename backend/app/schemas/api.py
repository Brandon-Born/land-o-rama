from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OpportunityListItem(BaseModel):
    id: str
    county: str
    state: str
    price: float
    acreage: float
    final_score: float
    base_score: float
    source_type: str
    created_at: datetime


class ScoreBreakdown(BaseModel):
    market_growth_score: float
    development_pressure_score: float
    accessibility_score: float
    liquidity_score: float
    risk_penalty_score: float
    base_score: float
    final_score: float
    personalization_score: float | None = None


class OpportunityDetail(BaseModel):
    id: str
    parcel_id: str
    county: str
    state: str
    price: float
    acreage: float
    source_type: str
    source_id: str
    source_name: str | None = None
    source_url: str | None = None
    is_excluded: bool
    exclusion_reason: str | None
    reason_codes: list[dict]
    caution_code: dict | None
    model_version: str | None = None
    blend_weight: float = 0.15
    score_breakdown: ScoreBreakdown
    created_at: datetime


class OpportunityListResponse(BaseModel):
    items: list[OpportunityListItem]
    total: int
    page: int
    page_size: int
    generated_at: datetime


class FeedbackInput(BaseModel):
    vote: Literal["up", "down"]
    note: str | None = None


class FeedbackResponse(BaseModel):
    status: Literal["ok"]
    feedback_id: str


class DigestSummary(BaseModel):
    id: str
    generated_at: datetime
    summary: str
    opportunity_ids: list[str]


class DigestsResponse(BaseModel):
    items: list[DigestSummary]


class ProviderEventStatus(BaseModel):
    provider: str
    status: str
    error_summary: str | None
    created_at: datetime


class RunStatus(BaseModel):
    id: str
    run_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    listings_ingested: int
    auctions_ingested: int
    candidates_scored: int
    excluded_count: int
    error_summary: str | None
    provider_events: list[ProviderEventStatus] = Field(default_factory=list)


class RunsResponse(BaseModel):
    items: list[RunStatus]


class RunNowResponse(BaseModel):
    run_id: str
    status: str


class SettingsResponse(BaseModel):
    state: str
    refresh_time: str
    mock_mode: bool
    disclaimers_enabled: bool = Field(default=True)
    regrid_configured: bool = False
    price_cap: float = 6000.0
    auction_source_mode: str = "mock"
    auction_csv_dir: str = "/Users/bborn/land-o-rama/data/auction_feeds"
    auction_csv_glob: str = "*.csv"
    auction_max_file_age_days: int = 14
    provider_timeout_seconds: float = 12.0
    provider_max_retries: int = 2
    market_metrics_cache_lookback_days: int = 30
    scraper_primary_source: str = "county_auction_scraper"
    scraper_mode: str = "download_first"
    scraper_target_counties: list[str] = Field(default_factory=list)
    scraper_last_success_at: datetime | None = None
    scraper_last_success_county: str | None = None
    scraper_parse_error_count: int = 0
    scraper_last_records_accepted: int = 0
    personalization_ready: bool = False
    feedback_labels_count: int = 0
    personalization_threshold: int = 50
    personalization_blend_weight: float = 0.15
    provider_health: list[ProviderEventStatus] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    refresh_time: str | None = None
    mock_mode: bool | None = None
