# Source Findings (Hunt Stabilization)

Date: 2026-02-15

## Goal
Identify viable Hunt County auction/tax-sale inventory sources that provide bid-like pricing (or equivalent) for stable `records_accepted > 0` outcomes.

## Candidate Sources Reviewed
1. LGBS property sales API
   - URL: `https://taxsales.lgbs.com/api/property_sales/`
   - Format: JSON
   - Strengths:
     - Structured payloads are parser-friendly.
     - Supports bid-like fields (`minimum_bid` style) suitable for `price_cap` filtering.
   - Risks:
     - Public API schema/versioning contract is not documented in-repo; parser must stay tolerant to field drift.
   - Decision: selected for ingestion as Hunt primary source.

2. PBFCM Hunt tax resale PDF
   - URL: `https://www.pbfcm.com/docs/taxdocs/resales/huntcountytaxresale.pdf`
   - Format: PDF
   - Strengths:
     - Existing production source with proven availability in current pipeline.
   - Risks:
     - Price field often reflects market/appraised value, which can produce zero accepted rows under cap.
   - Decision: retained as Hunt fallback source.

3. Hunt CAD ArcGIS parcel service
   - URL family: `services3.arcgis.com/.../HuntCADWebService/FeatureServer`
   - Format: ArcGIS JSON/FeatureService
   - Strengths:
     - Good parcel/enrichment context (acreage, valuation, geometry).
   - Risks:
     - Not a direct tax-sale inventory source.
   - Decision: reserve for enrichment, not primary auction ingestion.

4. Hunt Tax Office property search export
   - URL: `https://esearch.hctax.info/`
   - Format: web export/CSV workflow
   - Strengths:
     - Official county-managed search path.
   - Risks:
     - Automation path and schema stability less clear than API feed.
   - Decision: keep as contingency/manual reconciliation source.

## Implementation Decision (This Sprint)
- Add `lgbs_property_sales_v1` parser template.
- Add Hunt source-catalog entry for LGBS JSON with higher priority than PBFCM PDF fallback.
- Keep parser and validation tolerant to days where only market-value fallback is present.

## Handoff Notes
- If live runs fail at DNS/network layer for LGBS in the local environment, do not remove this source; capture the failure in provider diagnostics and keep PBFCM fallback active.
- Next agent should validate live reachability and field mapping against current payloads, then tune alias coverage as needed.

## Follow-up Verification (2026-02-15)
- Elevated network checks confirmed LGBS endpoint reachability and correct Hunt filter params (`state=TX`, `county=HUNT COUNTY`).
- Hunt payload rows frequently omit acreage; parser now attempts Hunt CAD `legal_acreage` lookup by `prop_id_text`/account identifier before rejection.
- With split-cap runtime (`price_cap=5000`, `ingestion_price_cap=15000`) and acreage enrichment in place, live Hunt validation passed:
  - `records_found=15`
  - `records_accepted=2`
  - report: `/Users/bborn/projects/land-o-rama/data/validation/live_check_hunt_after_two_tier_enrichment.json`
- Additional direct scraper probe showed intermittent/periodic `500 Internal Server Error` responses from the Hunt-filtered LGBS API URL; current accepted Hunt rows came from PBFCM fallback in that run.
