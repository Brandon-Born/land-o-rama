from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from statistics import median

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AuctionRaw,
    Digest,
    FeatureVector,
    ListingRaw,
    MarketMetricDaily,
    Opportunity,
    Parcel,
    ProviderRunEvent,
    RiskFlag,
    ScrapeArtifact,
    SyncRun,
)
from app.providers.auctions import AuctionProvider, build_auction_provider
from app.providers.enrichment import ParcelEnrichmentProvider
from app.providers.metrics import MarketMetricsProvider, build_market_metrics_provider
from app.providers.mock_data import CandidateRecord, CountyMetric, mock_candidates, mock_market_metrics
from app.scoring.engine import score_candidate
from app.services.personalization import count_labels, load_active_model, score_personalization
from app.services.settings import read_settings


def run_daily_pipeline(
    db: Session,
    *,
    auction_provider: AuctionProvider | None = None,
    enrichment_provider: ParcelEnrichmentProvider | None = None,  # kept for call-site compatibility
    metrics_provider: MarketMetricsProvider | None = None,
) -> SyncRun:
    settings = read_settings(db)
    runtime = get_settings()
    ingestion_price_cap = runtime.ingestion_price_cap
    run = SyncRun(run_type="daily", status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    degraded = False

    try:
        auction_candidates: list[CandidateRecord] = []
        market_metrics: list[CountyMetric] = []
        candidates: list[CandidateRecord] = []

        label_count = count_labels(db)
        personalization_model = None
        if label_count >= runtime.personalization_threshold:
            personalization_model = load_active_model()
            if personalization_model is None:
                degraded = True
                _record_provider_event(
                    db,
                    run.id,
                    provider="personalization_model",
                    status="degraded",
                    error_summary=(
                        f"Threshold met ({label_count} labels) but no active model artifact found at "
                        f"{runtime.personalization_model_path}."
                    ),
                )

        if settings.mock_mode:
            candidates = mock_candidates(settings.state)
            market_metrics = mock_market_metrics(date.today(), settings.state)
            _record_provider_event(db, run.id, provider="mock_listings", status="success")
            _record_provider_event(db, run.id, provider="mock_auctions", status="success")
            _record_provider_event(db, run.id, provider="mock_market_metrics", status="success")
        else:
            live_auction_provider = auction_provider or build_auction_provider(runtime)
            live_metrics_provider = metrics_provider or build_market_metrics_provider(runtime)
            catalog_warning = getattr(live_auction_provider, "catalog_warning", None)
            if catalog_warning:
                degraded = True
                _record_provider_event(
                    db,
                    run.id,
                    provider="county_source_catalog",
                    status="degraded",
                    error_summary=str(catalog_warning),
                )

            _ = enrichment_provider

            auction_candidates, auctions_error, auctions_warning = _fetch_live_auctions(
                live_auction_provider,
                state=settings.state,
                max_price=ingestion_price_cap,
            )
            scrape_artifacts = getattr(live_auction_provider, "last_artifacts", [])
            if scrape_artifacts:
                _persist_scrape_artifacts(
                    db,
                    run_id=run.id,
                    provider=live_auction_provider.provider_name,
                    artifacts=scrape_artifacts,
                )
            county_coverage = getattr(live_auction_provider, "last_county_coverage", [])
            if county_coverage:
                failed_counties = [item.county for item in county_coverage if item.status == "failed"]
                warning_counties = [item.county for item in county_coverage if item.status == "warning"]
                if failed_counties:
                    degraded = True
                if warning_counties:
                    degraded = True
                summary = "; ".join(
                    [
                        (
                            f"{item.county}: found={item.records_found}, accepted={item.records_accepted}, "
                            f"rejected={item.records_rejected}, min={item.min_price}, "
                            f"median={item.median_price}, max={item.max_price}, status={item.status}"
                        )
                        for item in county_coverage
                    ]
                )
                _record_provider_event(
                    db,
                    run.id,
                    provider="county_scrape_coverage",
                    status="degraded" if failed_counties or warning_counties else "success",
                    error_summary=summary,
                )
            if auctions_error:
                degraded = True
                _record_provider_event(
                    db,
                    run.id,
                    provider=live_auction_provider.provider_name,
                    status="failed",
                    error_summary=auctions_error,
                )
            elif auctions_warning:
                degraded = True
                _record_provider_event(
                    db,
                    run.id,
                    provider=live_auction_provider.provider_name,
                    status="degraded",
                    error_summary=auctions_warning,
                )
            else:
                _record_provider_event(
                    db,
                    run.id,
                    provider=live_auction_provider.provider_name,
                    status="success",
                )

            candidates = auction_candidates

            if not candidates:
                degraded = True
                run.status = "degraded"
                run.error_summary = "No new auction candidates available from scraper/county source."
                run.finished_at = datetime.now(UTC)
                _record_provider_event(
                    db,
                    run.id,
                    provider="scraper_no_new_data",
                    status="degraded",
                    error_summary="No new county auction records were available for this run.",
                )
                db.commit()
                return run

            candidate_counties = sorted({candidate.county for candidate in candidates})
            market_metrics, metrics_error = _fetch_live_market_metrics(
                live_metrics_provider,
                state=settings.state,
                counties=candidate_counties,
            )
            if not metrics_error and not market_metrics:
                metrics_error = "Market metrics provider returned no county metrics."

            if metrics_error:
                degraded = True
                _record_provider_event(
                    db,
                    run.id,
                    provider=live_metrics_provider.provider_name,
                    status="failed",
                    error_summary=metrics_error,
                )
                market_metrics = _load_cached_market_metrics(
                    db,
                    state=settings.state,
                    counties=candidate_counties,
                    lookback_days=runtime.market_metrics_cache_lookback_days,
                )
                if market_metrics:
                    _record_provider_event(
                        db,
                        run.id,
                        provider="market_metrics_cache",
                        status="degraded",
                        error_summary="Using cached market metrics because live provider failed.",
                    )
                else:
                    _record_provider_event(
                        db,
                        run.id,
                        provider="market_metrics_cache",
                        status="failed",
                        error_summary="No cached market metrics found for requested counties.",
                    )
            else:
                _record_provider_event(
                    db,
                    run.id,
                    provider=live_metrics_provider.provider_name,
                    status="success",
                )

        if not candidates:
            raise RuntimeError("No candidates available from live or fallback providers.")

        metric_map = {metric.county: metric for metric in market_metrics}
        _persist_metrics(db, market_metrics)

        run.listings_ingested = _persist_raw_records(db, candidates, source_type="listing")
        run.auctions_ingested = _persist_raw_records(db, candidates, source_type="auction")

        county_price_per_acre = _compute_price_per_acre_benchmarks(candidates)
        excluded_count = 0
        scored_count = 0

        counties_using_fallback_metric: set[str] = set()
        for candidate in candidates:
            if candidate.price > ingestion_price_cap:
                # Guardrail: enforce ingestion max price even if a provider sends out-of-policy data.
                continue
            scored_count += 1
            parcel = _upsert_parcel(db, candidate)
            metric = metric_map.get(candidate.county)
            if metric is None:
                degraded = True
                counties_using_fallback_metric.add(candidate.county)
                metric = _fallback_metric(candidate)
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
                source_name=candidate.source_name or candidate.source,
                source_url=candidate.source_url,
                county=candidate.county,
                state=candidate.state,
                price=candidate.price,
                acreage=candidate.acreage,
                base_score=scored.base_score,
                final_score=scored.final_score,
                personalization_score=None,
                model_version=None,
                blend_weight=runtime.personalization_blend_weight,
                is_excluded=scored.is_excluded,
                exclusion_reason=scored.exclusion_reason,
                reason_codes=scored.reason_codes,
                caution_code=scored.caution_code,
            )
            if not scored.is_excluded and personalization_model is not None:
                personalization_score = score_personalization(
                    personalization_model,
                    market_growth_score=scored.market_growth_score,
                    development_pressure_score=scored.development_pressure_score,
                    accessibility_score=scored.accessibility_score,
                    liquidity_score=scored.liquidity_score,
                    risk_penalty_score=scored.risk_penalty_score,
                    base_score=scored.base_score,
                    price=candidate.price,
                    acreage=candidate.acreage,
                )
                blended = (
                    (1 - runtime.personalization_blend_weight) * scored.final_score
                    + runtime.personalization_blend_weight * personalization_score
                )
                opportunity.final_score = round(max(0.0, min(100.0, blended)), 2)
                opportunity.personalization_score = personalization_score
                opportunity.model_version = personalization_model.version
            db.add(opportunity)

            _persist_risk_flags(db, run.id, parcel.id, candidate, scored.is_excluded)

        run.candidates_scored = scored_count
        run.excluded_count = excluded_count
        run.status = "degraded" if degraded else "success"
        run.finished_at = datetime.now(UTC)
        db.commit()

        if counties_using_fallback_metric:
            _record_provider_event(
                db,
                run.id,
                provider="market_metrics_fallback",
                status="degraded",
                error_summary=(
                    "Used deterministic fallback metrics for counties: "
                    + ", ".join(sorted(counties_using_fallback_metric))
                ),
            )
            db.commit()
        if personalization_model is not None:
            _record_provider_event(
                db,
                run.id,
                provider="personalization_model",
                status="success",
                error_summary=f"Applied model {personalization_model.version} with {label_count} labels.",
            )
            db.commit()

        _create_daily_digest(db, run.id)
        purge_old_data(db, months=24)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_summary = str(exc)
        run.finished_at = datetime.now(UTC)
        db.commit()
        _record_provider_event(db, run.id, provider="pipeline", status="failed", error_summary=str(exc))
        db.commit()
        raise

    return run


def purge_old_data(db: Session, months: int = 24) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=30 * months)
    db.execute(delete(ListingRaw).where(ListingRaw.created_at < cutoff).execution_options(synchronize_session=False))
    db.execute(delete(AuctionRaw).where(AuctionRaw.created_at < cutoff).execution_options(synchronize_session=False))
    db.execute(delete(FeatureVector).where(FeatureVector.created_at < cutoff).execution_options(synchronize_session=False))
    db.execute(delete(Opportunity).where(Opportunity.created_at < cutoff).execution_options(synchronize_session=False))
    db.execute(delete(Digest).where(Digest.generated_at < cutoff).execution_options(synchronize_session=False))


def latest_successful_run_id(db: Session) -> str | None:
    stmt = (
        select(SyncRun.id)
        .where(SyncRun.status.in_(["success", "degraded"]), SyncRun.candidates_scored > 0)
        .order_by(desc(SyncRun.started_at))
        .limit(1)
    )
    return db.scalar(stmt)


def _fetch_live_auctions(
    provider: AuctionProvider,
    *,
    state: str,
    max_price: float,
) -> tuple[list[CandidateRecord], str | None, str | None]:
    try:
        auctions = provider.fetch(state=state, max_price=max_price)
        stats = getattr(provider, "last_stats", None)
        warning: str | None = None
        if stats is not None and getattr(stats, "rejected_rows", 0) > 0:
            samples = getattr(stats, "error_samples", [])
            details = f"rejected_rows={stats.rejected_rows}"
            if samples:
                details += f"; samples={'; '.join(samples)}"
            warning = details
        return auctions, None, warning
    except Exception as exc:  # noqa: BLE001
        return [], str(exc), None


def _fetch_live_market_metrics(
    provider: MarketMetricsProvider,
    *,
    state: str,
    counties: list[str],
) -> tuple[list[CountyMetric], str | None]:
    try:
        metrics = provider.fetch(state=state, counties=counties, as_of_date=date.today())
        return metrics, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def _load_cached_market_metrics(
    db: Session,
    *,
    state: str,
    counties: list[str],
    lookback_days: int,
) -> list[CountyMetric]:
    if not counties:
        return []

    cutoff = date.today() - timedelta(days=max(0, lookback_days))
    rows = db.scalars(
        select(MarketMetricDaily)
        .where(
            MarketMetricDaily.state == state,
            MarketMetricDaily.county.in_(counties),
            MarketMetricDaily.as_of_date >= cutoff,
        )
        .order_by(desc(MarketMetricDaily.as_of_date))
    ).all()

    latest_by_county: dict[str, MarketMetricDaily] = {}
    for row in rows:
        if row.county not in latest_by_county:
            latest_by_county[row.county] = row

    return [
        CountyMetric(
            county=row.county,
            state=row.state,
            as_of_date=row.as_of_date,
            population_growth_1y=row.population_growth_1y,
            jobs_growth_1y=row.jobs_growth_1y,
            permit_growth_1y=row.permit_growth_1y,
            turnover_index=row.turnover_index,
        )
        for row in latest_by_county.values()
    ]


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
        payload = asdict(candidate)
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


def _persist_scrape_artifacts(
    db: Session,
    *,
    run_id: str,
    provider: str,
    artifacts: list,
) -> None:
    for artifact in artifacts:
        db.add(
            ScrapeArtifact(
                run_id=run_id,
                provider=provider,
                county=artifact.county,
                state=artifact.state,
                source_url=artifact.source_url,
                local_path=artifact.local_path,
                fetched_at=artifact.fetched_at,
                parser_version=artifact.parser_version,
                checksum_sha256=artifact.checksum_sha256,
                records_found=artifact.records_found,
                records_accepted=artifact.records_accepted,
                records_rejected=artifact.records_rejected,
                price_min=artifact.price_min,
                price_median=artifact.price_median,
                price_max=artifact.price_max,
            )
        )
    db.flush()


def _compute_price_per_acre_benchmarks(candidates: list[CandidateRecord]) -> dict[str, float]:
    by_county: dict[str, list[float]] = defaultdict(list)
    for candidate in candidates:
        by_county[candidate.county].append(candidate.price_per_acre)
    return {county: median(values) for county, values in by_county.items() if values}


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

    if selected:
        summary = (
            f"{len(selected)} opportunities surfaced from run {run_id}. "
            "Scores combine growth, development pressure, accessibility, liquidity, and risk burden."
        )
    else:
        summary = (
            f"No qualifying opportunities found for run {run_id}. "
            "All candidates were excluded or above configured thresholds."
        )

    db.add(
        Digest(
            summary=summary,
            opportunity_ids=[opportunity.id for opportunity in selected],
        )
    )


def _record_provider_event(
    db: Session,
    run_id: str,
    *,
    provider: str,
    status: str,
    error_summary: str | None = None,
) -> None:
    db.add(
        ProviderRunEvent(
            run_id=run_id,
            provider=provider,
            status=status,
            error_summary=error_summary,
        )
    )
    db.flush()
