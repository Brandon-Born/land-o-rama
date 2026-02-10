from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Digest, FeatureVector, Feedback, Opportunity, ProviderRunEvent, SyncRun
from app.schemas.api import (
    DigestSummary,
    DigestsResponse,
    FeedbackInput,
    FeedbackResponse,
    OpportunityDetail,
    OpportunityListItem,
    OpportunityListResponse,
    RunNowResponse,
    RunsResponse,
    RunStatus,
    ScoreBreakdown,
    ProviderEventStatus,
    SettingsResponse,
    SettingsUpdate,
)
from app.services.pipeline import latest_successful_run_id, run_daily_pipeline
from app.services.settings import read_settings, update_settings

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/opportunities", response_model=OpportunityListResponse)
def list_opportunities(
    min_score: float | None = Query(default=None),
    max_price: float = Query(default=5000.0),
    county: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> OpportunityListResponse:
    run_id = latest_successful_run_id(db)
    base_stmt = select(Opportunity).where(
        Opportunity.is_excluded.is_(False),
        Opportunity.price <= max_price,
    )
    if run_id:
        base_stmt = base_stmt.where(Opportunity.run_id == run_id)
    if min_score is not None:
        base_stmt = base_stmt.where(Opportunity.final_score >= min_score)
    if county:
        base_stmt = base_stmt.where(func.lower(Opportunity.county) == county.lower())

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.scalar(total_stmt) or 0
    items_stmt = (
        base_stmt.order_by(desc(Opportunity.final_score))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(items_stmt).all()
    payload = [
        OpportunityListItem(
            id=item.id,
            county=item.county,
            state=item.state,
            price=item.price,
            acreage=item.acreage,
            final_score=item.final_score,
            base_score=item.base_score,
            source_type=item.source_type,
            created_at=item.created_at,
        )
        for item in items
    ]
    return OpportunityListResponse(
        items=payload,
        total=total,
        page=page,
        page_size=page_size,
        generated_at=datetime.now(UTC),
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: str, db: Session = Depends(get_db)) -> OpportunityDetail:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    feature = db.scalar(
        select(FeatureVector)
        .where(
            FeatureVector.run_id == opportunity.run_id,
            FeatureVector.parcel_id == opportunity.parcel_id,
        )
        .order_by(desc(FeatureVector.created_at))
        .limit(1)
    )
    if not feature:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feature vector missing")

    return OpportunityDetail(
        id=opportunity.id,
        parcel_id=opportunity.parcel_id,
        county=opportunity.county,
        state=opportunity.state,
        price=opportunity.price,
        acreage=opportunity.acreage,
        source_type=opportunity.source_type,
        source_id=opportunity.source_id,
        source_name=opportunity.source_name,
        source_url=opportunity.source_url,
        is_excluded=opportunity.is_excluded,
        exclusion_reason=opportunity.exclusion_reason,
        reason_codes=opportunity.reason_codes,
        caution_code=opportunity.caution_code,
        model_version=opportunity.model_version,
        blend_weight=opportunity.blend_weight,
        score_breakdown=ScoreBreakdown(
            market_growth_score=feature.market_growth_score,
            development_pressure_score=feature.development_pressure_score,
            accessibility_score=feature.accessibility_score,
            liquidity_score=feature.liquidity_score,
            risk_penalty_score=feature.risk_penalty_score,
            base_score=opportunity.base_score,
            final_score=opportunity.final_score,
            personalization_score=opportunity.personalization_score,
        ),
        created_at=opportunity.created_at,
    )


@router.post("/opportunities/{opportunity_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    opportunity_id: str,
    payload: FeedbackInput,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    feedback = Feedback(opportunity_id=opportunity_id, vote=payload.vote, note=payload.note)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return FeedbackResponse(status="ok", feedback_id=feedback.id)


@router.get("/digests/latest", response_model=DigestSummary)
def latest_digest(db: Session = Depends(get_db)) -> DigestSummary:
    digest = db.scalar(select(Digest).order_by(desc(Digest.generated_at)).limit(1))
    if not digest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No digest available")
    return DigestSummary(
        id=digest.id,
        generated_at=digest.generated_at,
        summary=digest.summary,
        opportunity_ids=digest.opportunity_ids,
    )


@router.get("/digests", response_model=DigestsResponse)
def list_digests(db: Session = Depends(get_db)) -> DigestsResponse:
    digests = db.scalars(select(Digest).order_by(desc(Digest.generated_at)).limit(30)).all()
    return DigestsResponse(
        items=[
            DigestSummary(
                id=digest.id,
                generated_at=digest.generated_at,
                summary=digest.summary,
                opportunity_ids=digest.opportunity_ids,
            )
            for digest in digests
        ]
    )


@router.post("/jobs/run-daily", response_model=RunNowResponse)
def run_daily(db: Session = Depends(get_db)) -> RunNowResponse:
    run = run_daily_pipeline(db)
    return RunNowResponse(run_id=run.id, status=run.status)


@router.get("/runs", response_model=RunsResponse)
def list_runs(db: Session = Depends(get_db)) -> RunsResponse:
    runs = db.scalars(select(SyncRun).order_by(desc(SyncRun.started_at)).limit(50)).all()
    run_ids = [run.id for run in runs]
    events_by_run: dict[str, list[ProviderRunEvent]] = {run_id: [] for run_id in run_ids}
    if run_ids:
        events = db.scalars(
            select(ProviderRunEvent)
            .where(ProviderRunEvent.run_id.in_(run_ids))
            .order_by(ProviderRunEvent.created_at.desc())
        ).all()
        for event in events:
            bucket = events_by_run.get(event.run_id)
            if bucket is not None and len(bucket) < 6:
                bucket.append(event)

    return RunsResponse(
        items=[
            RunStatus(
                id=run.id,
                run_type=run.run_type,
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                listings_ingested=run.listings_ingested,
                auctions_ingested=run.auctions_ingested,
                candidates_scored=run.candidates_scored,
                excluded_count=run.excluded_count,
                error_summary=run.error_summary,
                provider_events=[
                    ProviderEventStatus(
                        provider=event.provider,
                        status=event.status,
                        error_summary=event.error_summary,
                        created_at=event.created_at,
                    )
                    for event in events_by_run.get(run.id, [])
                ],
            )
            for run in runs
        ]
    )


@router.get("/settings", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)) -> SettingsResponse:
    return read_settings(db)


@router.put("/settings", response_model=SettingsResponse)
def put_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsResponse:
    return update_settings(db, payload)
