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


class OpportunityDetail(BaseModel):
    id: str
    parcel_id: str
    county: str
    state: str
    price: float
    acreage: float
    source_type: str
    source_id: str
    is_excluded: bool
    exclusion_reason: str | None
    reason_codes: list[dict]
    caution_code: dict | None
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


class SettingsUpdate(BaseModel):
    refresh_time: str | None = None
    mock_mode: bool | None = None
