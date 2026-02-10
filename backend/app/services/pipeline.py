from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import median

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models import (
    AuctionRaw,
    Digest,
    FeatureVector,
    ListingRaw,
    MarketMetricDaily,
    Opportunity,
    Parcel,
    RiskFlag,
    SyncRun,
)
from app.providers.mock_data import CandidateRecord, CountyMetric, mock_candidates, mock_market_metrics
from app.scoring.engine import score_candidate
from app.services.settings import read_settings


def run_daily_pipeline(db: Session) -> SyncRun:
    settings = read_settings(db)
    run = SyncRun(run_type="daily", status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        candidates = mock_candidates(settings.state)
        metrics = mock_market_metrics(date.today(), settings.state)
        metric_map = {metric.county: metric for metric in metrics}
        _persist_metrics(db, metrics)

        run.listings_ingested = _persist_raw_records(db, candidates, source_type="listing")
        run.auctions_ingested = _persist_raw_records(db, candidates, source_type="auction")

        county_price_per_acre = _compute_price_per_acre_benchmarks(candidates)
        excluded_count = 0
        scored_count = 0

        for candidate in candidates:
            if candidate.price > 6000:
                continue
            scored_count += 1
            parcel = _upsert_parcel(db, candidate)
            metric = metric_map.get(candidate.county) or _fallback_metric(candidate)
            scored = score_candidate(
                candidate,
                metric,
                county_median_price_per_acre=county_price_per_acre.get(candidate.county),
            )

            feature_vector = FeatureVector(
                parcel_id=parcel.id,
                run_id=run.id,
                as_of_date=date.today(),
                market_growth_score=scored.market_growth_score,
                development_pressure_score=scored.development_pressure_score,
                accessibility_score=scored.accessibility_score,
                liquidity_score=scored.liquidity_score,
                risk_penalty_score=scored.risk_penalty_score,
            )
            db.add(feature_vector)

            if scored.is_excluded:
                excluded_count += 1

            opportunity = Opportunity(
                run_id=run.id,
                parcel_id=parcel.id,
                source_type=candidate.source_type,
                source_id=candidate.external_id,
                county=candidate.county,
                state=candidate.state,
                price=candidate.price,
                acreage=candidate.acreage,
                base_score=scored.base_score,
                final_score=scored.final_score,
                is_excluded=scored.is_excluded,
                exclusion_reason=scored.exclusion_reason,
                reason_codes=scored.reason_codes,
                caution_code=scored.caution_code,
            )
            db.add(opportunity)

            _persist_risk_flags(db, run.id, parcel.id, candidate, scored.is_excluded)

        run.candidates_scored = scored_count
        run.excluded_count = excluded_count
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        db.commit()

        _create_daily_digest(db, run.id)
        purge_old_data(db, months=24)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_summary = str(exc)
        run.finished_at = datetime.now(UTC)
        db.commit()
        raise

    return run


def purge_old_data(db: Session, months: int = 24) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=30 * months)
    db.execute(delete(ListingRaw).where(ListingRaw.created_at < cutoff))
    db.execute(delete(AuctionRaw).where(AuctionRaw.created_at < cutoff))
    db.execute(delete(FeatureVector).where(FeatureVector.created_at < cutoff))
    db.execute(delete(Opportunity).where(Opportunity.created_at < cutoff))
    db.execute(delete(Digest).where(Digest.generated_at < cutoff))


def latest_successful_run_id(db: Session) -> str | None:
    stmt = (
        select(SyncRun.id)
        .where(SyncRun.status == "success")
        .order_by(desc(SyncRun.started_at))
        .limit(1)
    )
    return db.scalar(stmt)


def _persist_metrics(db: Session, metrics: list[CountyMetric]) -> None:
    for metric in metrics:
        exists = db.scalar(
            select(MarketMetricDaily.id).where(
                MarketMetricDaily.county == metric.county,
                MarketMetricDaily.state == metric.state,
                MarketMetricDaily.as_of_date == metric.as_of_date,
            )
        )
        if exists:
            continue
        db.add(
            MarketMetricDaily(
                county=metric.county,
                state=metric.state,
                as_of_date=metric.as_of_date,
                population_growth_1y=metric.population_growth_1y,
                jobs_growth_1y=metric.jobs_growth_1y,
                permit_growth_1y=metric.permit_growth_1y,
                turnover_index=metric.turnover_index,
            )
        )


def _persist_raw_records(db: Session, candidates: list[CandidateRecord], source_type: str) -> int:
    count = 0
    for candidate in candidates:
        if candidate.source_type != source_type:
            continue
        count += 1
        payload = candidate.__dict__
        if source_type == "listing":
            db.add(
                ListingRaw(
                    source=candidate.source,
                    external_id=candidate.external_id,
                    county=candidate.county,
                    state=candidate.state,
                    price=candidate.price,
                    payload=payload,
                )
            )
        else:
            db.add(
                AuctionRaw(
                    source=candidate.source,
                    external_id=candidate.external_id,
                    county=candidate.county,
                    state=candidate.state,
                    price=candidate.price,
                    payload=payload,
                )
            )
    db.flush()
    return count


def _upsert_parcel(db: Session, candidate: CandidateRecord) -> Parcel:
    parcel = db.scalar(select(Parcel).where(Parcel.parcel_key == candidate.parcel_key))
    if parcel:
        parcel.county = candidate.county
        parcel.state = candidate.state
        parcel.acreage = candidate.acreage
        parcel.latitude = candidate.latitude
        parcel.longitude = candidate.longitude
        parcel.zoning = candidate.zoning
        parcel.legal_access = candidate.legal_access
        parcel.utilities_hint = candidate.utilities_hint
        parcel.flood_risk_level = candidate.flood_risk_level
        parcel.wetland_risk_level = candidate.wetland_risk_level
        return parcel

    parcel = Parcel(
        parcel_key=candidate.parcel_key,
        county=candidate.county,
        state=candidate.state,
        acreage=candidate.acreage,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        zoning=candidate.zoning,
        legal_access=candidate.legal_access,
        utilities_hint=candidate.utilities_hint,
        flood_risk_level=candidate.flood_risk_level,
        wetland_risk_level=candidate.wetland_risk_level,
    )
    db.add(parcel)
    db.flush()
    return parcel


def _persist_risk_flags(
    db: Session,
    run_id: str,
    parcel_id: str,
    candidate: CandidateRecord,
    is_excluded: bool,
) -> None:
    if not candidate.legal_access:
        db.add(
            RiskFlag(
                parcel_id=parcel_id,
                run_id=run_id,
                flag="NO_LEGAL_ACCESS",
                severity=10,
                is_exclusionary=True,
            )
        )
    db.add(
        RiskFlag(
            parcel_id=parcel_id,
            run_id=run_id,
            flag="FLOOD_RISK",
            severity=candidate.flood_risk_level,
            is_exclusionary=is_excluded and candidate.flood_risk_level >= 7,
        )
    )
    db.add(
        RiskFlag(
            parcel_id=parcel_id,
            run_id=run_id,
            flag="WETLAND_RISK",
            severity=candidate.wetland_risk_level,
            is_exclusionary=is_excluded and candidate.wetland_risk_level >= 7,
        )
    )


def _compute_price_per_acre_benchmarks(candidates: list[CandidateRecord]) -> dict[str, float]:
    by_county: dict[str, list[float]] = defaultdict(list)
    for candidate in candidates:
        by_county[candidate.county].append(candidate.price_per_acre)
    return {county: median(values) for county, values in by_county.items()}


def _fallback_metric(candidate: CandidateRecord) -> CountyMetric:
    return CountyMetric(
        county=candidate.county,
        state=candidate.state,
        as_of_date=date.today(),
        population_growth_1y=1.0,
        jobs_growth_1y=1.0,
        permit_growth_1y=1.0,
        turnover_index=50.0,
    )


def _create_daily_digest(db: Session, run_id: str) -> None:
    latest_non_excluded = db.scalars(
        select(Opportunity)
        .where(Opportunity.run_id == run_id, Opportunity.is_excluded.is_(False), Opportunity.price <= 5000)
        .order_by(desc(Opportunity.final_score))
    ).all()

    top_by_county: dict[str, Opportunity] = {}
    remainder: list[Opportunity] = []
    for opportunity in latest_non_excluded:
        if opportunity.county not in top_by_county:
            top_by_county[opportunity.county] = opportunity
        else:
            remainder.append(opportunity)

    selected: list[Opportunity] = list(top_by_county.values())
    if len(selected) < 20:
        selected.extend(remainder[: 20 - len(selected)])
    selected = selected[:20]

    summary = (
        f"{len(selected)} opportunities surfaced from run {run_id}. "
        "Scores combine growth, development pressure, accessibility, liquidity, and risk burden."
    )

    db.add(
        Digest(
            summary=summary,
            opportunity_ids=[opportunity.id for opportunity in selected],
        )
    )
