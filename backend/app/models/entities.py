from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ListingRaw(Base):
    __tablename__ = "listings_raw"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    county: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    price: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuctionRaw(Base):
    __tablename__ = "auctions_raw"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    county: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    price: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parcel_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    county: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    acreage: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    zoning: Mapped[str] = mapped_column(String(64))
    legal_access: Mapped[bool] = mapped_column(Boolean, default=True)
    utilities_hint: Mapped[str] = mapped_column(String(128), default="unknown")
    flood_risk_level: Mapped[int] = mapped_column(Integer, default=0)
    wetland_risk_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="parcel")


class MarketMetricDaily(Base):
    __tablename__ = "market_metrics_daily"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    county: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    population_growth_1y: Mapped[float] = mapped_column(Float)
    jobs_growth_1y: Mapped[float] = mapped_column(Float)
    permit_growth_1y: Mapped[float] = mapped_column(Float)
    turnover_index: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeatureVector(Base):
    __tablename__ = "feature_vectors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parcel_id: Mapped[str] = mapped_column(ForeignKey("parcels.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    market_growth_score: Mapped[float] = mapped_column(Float)
    development_pressure_score: Mapped[float] = mapped_column(Float)
    accessibility_score: Mapped[float] = mapped_column(Float)
    liquidity_score: Mapped[float] = mapped_column(Float)
    risk_penalty_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_type: Mapped[str] = mapped_column(String(32), default="daily")
    status: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    listings_ingested: Mapped[int] = mapped_column(Integer, default=0)
    auctions_ingested: Mapped[int] = mapped_column(Integer, default=0)
    candidates_scored: Mapped[int] = mapped_column(Integer, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="run")
    provider_events: Mapped[list["ProviderRunEvent"]] = relationship(back_populates="run")
    scrape_artifacts: Mapped[list["ScrapeArtifact"]] = relationship(back_populates="run")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    parcel_id: Mapped[str] = mapped_column(ForeignKey("parcels.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    county: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    price: Mapped[float] = mapped_column(Float, index=True)
    acreage: Mapped[float] = mapped_column(Float)
    base_score: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float, index=True)
    personalization_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    blend_weight: Mapped[float] = mapped_column(Float, default=0.15)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reason_codes: Mapped[list[dict]] = mapped_column(JSON, default=list)
    caution_code: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    parcel: Mapped[Parcel] = relationship(back_populates="opportunities")
    run: Mapped[SyncRun] = relationship(back_populates="opportunities")


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parcel_id: Mapped[str] = mapped_column(ForeignKey("parcels.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    flag: Mapped[str] = mapped_column(String(64))
    severity: Mapped[int] = mapped_column(Integer)
    is_exclusionary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    vote: Mapped[str] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    summary: Mapped[str] = mapped_column(Text)
    opportunity_ids: Mapped[list[str]] = mapped_column(JSON)


class ConfigKV(Base):
    __tablename__ = "config_kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProviderRunEvent(Base):
    __tablename__ = "provider_run_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    run: Mapped[SyncRun] = relationship(back_populates="provider_events")


class ScrapeArtifact(Base):
    __tablename__ = "scrape_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    county: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    source_url: Mapped[str] = mapped_column(String(1024))
    local_path: Mapped[str] = mapped_column(String(1024))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    parser_version: Mapped[str] = mapped_column(String(64))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_accepted: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    run: Mapped[SyncRun] = relationship(back_populates="scrape_artifacts")


class ModelTrainingRun(Base):
    __tablename__ = "model_training_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    labels_used: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
