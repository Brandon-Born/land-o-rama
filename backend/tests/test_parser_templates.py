from __future__ import annotations

from pathlib import Path

from app.providers.parser_templates import LgbsPropertySalesParser, PdfTaxsaleParser


def test_pdf_parser_supports_text_snapshot_fixture() -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "hunt" / "hunt_pdf_snapshot_excerpt.txt"
    parser = PdfTaxsaleParser()

    result = parser.parse(
        file_path=fixture,
        county="Hunt",
        state="TX",
        max_price=100_000,
        source_name="Hunt Snapshot Fixture",
        provider_name="county_auction_scraper",
    )

    assert result.records_found == 3
    assert result.records_accepted == 3
    assert result.records_rejected == 0
    assert result.records_filtered_price == 0
    assert all(candidate.auction_entry_price is None for candidate in result.candidates)
    assert all(candidate.observed_market_value is not None for candidate in result.candidates)
    assert all(candidate.price_source == "market_value_fallback" for candidate in result.candidates)


def test_pdf_parser_prefers_entry_bid_over_market_value(tmp_path, monkeypatch) -> None:
    source_pdf = tmp_path / "hunt_resale.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n%fixture\n")
    monkeypatch.setattr(
        "app.providers.parser_templates._extract_pdf_text",
        lambda _: (
            "12345 S4385 ORIG TOWN OF GREENVILLE LOT 1 ACRES 0.25 "
            "MINIMUM BID $2,400.00 MARKET VALUE $18,000.00\n"
            "12346 S4385 ORIG TOWN OF GREENVILLE LOT 2 ACRES 0.50 "
            "MINIMUM BID $7,500.00 MARKET VALUE $25,000.00"
        ),
    )
    parser = PdfTaxsaleParser()

    result = parser.parse(
        file_path=source_pdf,
        county="Hunt",
        state="TX",
        max_price=5_000,
        source_name="Hunt Bid Fixture",
        provider_name="county_auction_scraper",
    )

    assert result.records_found == 2
    assert result.records_accepted == 1
    assert result.records_rejected == 0
    assert result.records_filtered_price == 1
    assert result.parsed_prices == [2400.0, 7500.0]
    assert result.rejection_reasons["price_cap"] == 1
    candidate = result.candidates[0]
    assert candidate.price == 2400.0
    assert candidate.auction_entry_price == 2400.0
    assert candidate.observed_market_value == 18000.0
    assert candidate.price_source == "auction_entry_price"


def test_lgbs_parser_hunt_filter_and_price_selection() -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "hunt" / "lgbs_property_sales_sample.json"
    parser = LgbsPropertySalesParser()

    result = parser.parse(
        file_path=fixture,
        county="Hunt",
        state="TX",
        max_price=5_000,
        source_name="LGBS Fixture",
        provider_name="county_auction_scraper",
    )

    assert result.records_found == 4
    assert result.records_rejected == 1
    assert result.records_accepted == 2
    assert result.records_filtered_price == 1
    assert result.parsed_prices == [2450.0, 4800.0, 7200.0]
    assert result.rejection_reasons["county_mismatch"] == 1
    assert result.rejection_reasons["price_cap"] == 1
    assert len(result.candidates) == 2

    first = result.candidates[0]
    assert first.external_id == "HUNT-1001"
    assert first.price == 2450.0
    assert first.auction_entry_price == 2450.0
    assert first.observed_market_value == 18000.0
    assert first.price_source == "auction_entry_price"

    second = result.candidates[1]
    assert second.external_id == "HUNT-1002"
    assert second.price == 4800.0
    assert second.auction_entry_price is None
    assert second.observed_market_value == 4800.0
    assert second.price_source == "market_value_fallback"
    assert second.latitude == 33.1479
    assert second.longitude == -96.1312


def test_lgbs_parser_enriches_hunt_acreage_from_resolver(tmp_path) -> None:
    fixture = tmp_path / "lgbs_missing_acreage.json"
    fixture.write_text(
        """
{
  "results": [
    {
      "uid": "HUNT-ACRE-1",
      "county": "HUNT COUNTY",
      "state": "TX",
      "account_nbr": "32650",
      "minimum_bid": null,
      "value": "4500.00",
      "geometry": {"type": "Point", "coordinates": [-96.11, 33.13]}
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    parser = LgbsPropertySalesParser(hunt_acreage_resolver=lambda _: 1.635)

    result = parser.parse(
        file_path=fixture,
        county="Hunt",
        state="TX",
        max_price=5_000,
        source_name="LGBS Fixture",
        provider_name="county_auction_scraper",
    )

    assert result.records_found == 1
    assert result.records_rejected == 0
    assert result.records_accepted == 1
    assert result.records_filtered_price == 0
    assert result.candidates[0].acreage == 1.635
    assert result.candidates[0].price == 4500.0
