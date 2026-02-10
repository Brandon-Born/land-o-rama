from datetime import date

from app.providers.mock_data import CandidateRecord, CountyMetric
from app.scoring.engine import evaluate_exclusions, score_candidate


def build_candidate(**kwargs) -> CandidateRecord:
    base = {
        "source_type": "listing",
        "source": "mock",
        "external_id": "X-1",
        "parcel_key": "TX-TEST-001",
        "county": "Travis",
        "state": "TX",
        "price": 3000.0,
        "acreage": 0.2,
        "latitude": 30.0,
        "longitude": -97.0,
        "zoning": "residential",
        "legal_access": True,
        "utilities_hint": "nearby",
        "flood_risk_level": 2,
        "wetland_risk_level": 1,
        "road_distance_miles": 0.4,
        "days_on_market": 14,
        "price_per_acre": 12000.0,
    }
    base.update(kwargs)
    return CandidateRecord(**base)


def metric() -> CountyMetric:
    return CountyMetric(
        county="Travis",
        state="TX",
        as_of_date=date(2026, 2, 10),
        population_growth_1y=2.0,
        jobs_growth_1y=2.0,
        permit_growth_1y=2.5,
        turnover_index=60.0,
    )


def test_exclusion_no_legal_access() -> None:
    candidate = build_candidate(legal_access=False)
    assert evaluate_exclusions(candidate) == "NO_LEGAL_ACCESS"


def test_exclusion_non_buildable_zoning() -> None:
    candidate = build_candidate(zoning="agriculture")
    assert evaluate_exclusions(candidate) == "NON_BUILDABLE_ZONING"


def test_score_candidate_non_excluded() -> None:
    candidate = build_candidate()
    result = score_candidate(candidate, metric())
    assert result.is_excluded is False
    assert result.final_score > 0
    assert len(result.reason_codes) == 3


def test_score_candidate_excluded_sets_zero() -> None:
    candidate = build_candidate(flood_risk_level=8)
    result = score_candidate(candidate, metric())
    assert result.is_excluded is True
    assert result.exclusion_reason == "SEVERE_FLOOD_CONSTRAINT"
    assert result.final_score == 0.0
