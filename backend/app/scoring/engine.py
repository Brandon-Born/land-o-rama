from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.mock_data import CandidateRecord, CountyMetric

ALLOWED_ZONING = {"residential", "single_family", "mixed_use_residential"}
MAX_FLOOD_RISK = 7
MAX_WETLAND_RISK = 7


@dataclass(slots=True)
class ScoreResult:
    market_growth_score: float
    development_pressure_score: float
    accessibility_score: float
    liquidity_score: float
    risk_penalty_score: float
    base_score: float
    value_modifier: float
    final_score: float
    is_excluded: bool
    exclusion_reason: str | None
    reason_codes: list[dict[str, Any]]
    caution_code: dict[str, Any] | None


def _clamp(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 2)


def evaluate_exclusions(candidate: CandidateRecord) -> str | None:
    if not candidate.legal_access:
        return "NO_LEGAL_ACCESS"
    if candidate.flood_risk_level >= MAX_FLOOD_RISK:
        return "SEVERE_FLOOD_CONSTRAINT"
    if candidate.wetland_risk_level >= MAX_WETLAND_RISK:
        return "SEVERE_WETLAND_CONSTRAINT"
    if candidate.zoning.lower() not in ALLOWED_ZONING:
        return "NON_BUILDABLE_ZONING"
    critical_fields = [
        candidate.county,
        candidate.state,
        candidate.parcel_key,
        candidate.source,
        candidate.external_id,
    ]
    if any(not value for value in critical_fields) or candidate.price <= 0:
        return "MISSING_CRITICAL_FIELDS"
    return None


def score_candidate(
    candidate: CandidateRecord,
    metric: CountyMetric,
    county_median_price_per_acre: float | None = None,
) -> ScoreResult:
    exclusion_reason = evaluate_exclusions(candidate)

    market_growth = _clamp(
        45 + (metric.population_growth_1y * 10) + (metric.jobs_growth_1y * 8)
    )
    development_pressure = _clamp(40 + (metric.permit_growth_1y * 12))
    accessibility = _clamp(
        95
        - (candidate.road_distance_miles * 18)
        + (8 if candidate.utilities_hint in {"nearby", "city_frontage"} else -5)
    )
    liquidity = _clamp((metric.turnover_index * 0.8) + max(0, 25 - candidate.days_on_market * 0.4))
    risk_penalty = _clamp(
        (candidate.flood_risk_level * 7.5)
        + (candidate.wetland_risk_level * 7.0)
        + (10 if candidate.utilities_hint == "none" else 0)
    )

    base_score = _clamp(
        (0.35 * market_growth)
        + (0.25 * development_pressure)
        + (0.20 * accessibility)
        + (0.10 * liquidity)
        + (0.10 * (100 - risk_penalty))
    )

    if county_median_price_per_acre and county_median_price_per_acre > 0:
        discount_ratio = (county_median_price_per_acre - candidate.price_per_acre) / county_median_price_per_acre
        value_modifier = round(max(-10.0, min(10.0, discount_ratio * 40)), 2)
    else:
        value_modifier = _clamp(60 - (candidate.price_per_acre / 500)) - 50
        value_modifier = round(max(-10.0, min(10.0, value_modifier)), 2)
    final_score = _clamp(base_score + value_modifier)

    components = [
        ("MARKET_GROWTH", market_growth),
        ("DEVELOPMENT_PRESSURE", development_pressure),
        ("ACCESSIBILITY", accessibility),
        ("LIQUIDITY", liquidity),
        ("LOW_RISK_PROFILE", 100 - risk_penalty),
    ]
    top_positive = sorted(components, key=lambda item: item[1], reverse=True)[:3]
    reason_codes = [
        {"code": code, "label": code.replace("_", " ").title(), "direction": "positive", "impact": score}
        for code, score in top_positive
    ]

    caution_score = risk_penalty
    caution_code = (
        {
            "code": "RISK_BURDEN",
            "label": "Risk Burden",
            "direction": "caution",
            "impact": caution_score,
        }
        if caution_score > 0
        else None
    )

    if exclusion_reason:
        final_score = 0.0

    return ScoreResult(
        market_growth_score=market_growth,
        development_pressure_score=development_pressure,
        accessibility_score=accessibility,
        liquidity_score=liquidity,
        risk_penalty_score=risk_penalty,
        base_score=base_score,
        value_modifier=value_modifier,
        final_score=final_score,
        is_excluded=exclusion_reason is not None,
        exclusion_reason=exclusion_reason,
        reason_codes=reason_codes,
        caution_code=caution_code,
    )
