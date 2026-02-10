from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class CandidateRecord:
    source_type: str
    source: str
    external_id: str
    parcel_key: str
    county: str
    state: str
    price: float
    acreage: float
    latitude: float
    longitude: float
    zoning: str
    legal_access: bool
    utilities_hint: str
    flood_risk_level: int
    wetland_risk_level: int
    road_distance_miles: float
    days_on_market: int
    price_per_acre: float
    source_name: str | None = None
    source_url: str | None = None


@dataclass(slots=True)
class CountyMetric:
    county: str
    state: str
    as_of_date: date
    population_growth_1y: float
    jobs_growth_1y: float
    permit_growth_1y: float
    turnover_index: float


def mock_candidates(state: str = "TX") -> list[CandidateRecord]:
    return [
        CandidateRecord(
            source_type="listing",
            source="mock_listings",
            external_id="LST-1001",
            source_name="Mock Listings",
            source_url="https://example.test/listings/LST-1001",
            parcel_key="TX-TRAVIS-001",
            county="Travis",
            state=state,
            price=4200.0,
            acreage=0.21,
            latitude=30.4729,
            longitude=-97.6819,
            zoning="residential",
            legal_access=True,
            utilities_hint="nearby",
            flood_risk_level=2,
            wetland_risk_level=1,
            road_distance_miles=0.2,
            days_on_market=18,
            price_per_acre=20000.0,
        ),
        CandidateRecord(
            source_type="auction",
            source="mock_auctions",
            external_id="AUC-2001",
            source_name="Mock Auctions",
            source_url="https://example.test/auctions/AUC-2001",
            parcel_key="TX-BELL-014",
            county="Bell",
            state=state,
            price=1900.0,
            acreage=0.32,
            latitude=31.1171,
            longitude=-97.7278,
            zoning="single_family",
            legal_access=True,
            utilities_hint="unknown",
            flood_risk_level=4,
            wetland_risk_level=2,
            road_distance_miles=0.5,
            days_on_market=5,
            price_per_acre=5937.0,
        ),
        CandidateRecord(
            source_type="listing",
            source="mock_listings",
            external_id="LST-1002",
            source_name="Mock Listings",
            source_url="https://example.test/listings/LST-1002",
            parcel_key="TX-HARRIS-032",
            county="Harris",
            state=state,
            price=5100.0,
            acreage=0.15,
            latitude=29.7604,
            longitude=-95.3698,
            zoning="residential",
            legal_access=True,
            utilities_hint="city_frontage",
            flood_risk_level=7,
            wetland_risk_level=3,
            road_distance_miles=0.1,
            days_on_market=32,
            price_per_acre=34000.0,
        ),
        CandidateRecord(
            source_type="auction",
            source="mock_auctions",
            external_id="AUC-2002",
            source_name="Mock Auctions",
            source_url="https://example.test/auctions/AUC-2002",
            parcel_key="TX-CAMERON-011",
            county="Cameron",
            state=state,
            price=2400.0,
            acreage=0.28,
            latitude=26.1293,
            longitude=-97.6311,
            zoning="agriculture",
            legal_access=True,
            utilities_hint="none",
            flood_risk_level=5,
            wetland_risk_level=4,
            road_distance_miles=2.3,
            days_on_market=11,
            price_per_acre=8571.0,
        ),
        CandidateRecord(
            source_type="listing",
            source="mock_listings",
            external_id="LST-1003",
            source_name="Mock Listings",
            source_url="https://example.test/listings/LST-1003",
            parcel_key="TX-BEXAR-022",
            county="Bexar",
            state=state,
            price=3500.0,
            acreage=0.24,
            latitude=29.4241,
            longitude=-98.4936,
            zoning="single_family",
            legal_access=False,
            utilities_hint="nearby",
            flood_risk_level=3,
            wetland_risk_level=1,
            road_distance_miles=0.6,
            days_on_market=44,
            price_per_acre=14583.0,
        ),
    ]


def mock_market_metrics(as_of_date: date, state: str = "TX") -> list[CountyMetric]:
    return [
        CountyMetric("Travis", state, as_of_date, 2.4, 2.2, 3.0, 67.0),
        CountyMetric("Bell", state, as_of_date, 1.8, 1.5, 2.2, 58.0),
        CountyMetric("Harris", state, as_of_date, 1.4, 1.1, 1.5, 63.0),
        CountyMetric("Cameron", state, as_of_date, 0.9, 0.8, 1.2, 42.0),
        CountyMetric("Bexar", state, as_of_date, 1.7, 1.2, 1.8, 55.0),
    ]
