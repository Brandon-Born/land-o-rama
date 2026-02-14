# Implementation Backlog (Execution Order)

This backlog is ordered and decision-complete for v1.
Pivot effective `2026-02-13`: county auction scraping is now the primary live source, and RapidAPI functionality is deprecated.

## Phase 1: Project Scaffold (Complete)
Deliverables:
- Backend app skeleton (`FastAPI`, config, health endpoint).
- Frontend app skeleton (`React + TypeScript + Vite`).
- SQLite setup + Alembic migration baseline.
- Local run scripts and `.env.example`.

Acceptance:
- Backend and frontend boot locally.
- Health endpoint returns success.
- Initial migration creates base schema.

## Phase 2: Canonical Data Model + Mock Ingestion (Complete)
Deliverables:
- Canonical tables for listings, auctions, parcels, metrics, opportunities, feedback, runs.
- Mock providers with representative fixtures.
- Normalization and dedupe pipeline.

Acceptance:
- Mock run ingests records and stores normalized entities.
- Duplicate payloads do not create duplicate parcels.

## Phase 3: Scoring Engine + Exclusions (Complete)
Deliverables:
- Hard exclusion evaluator.
- Factor score computation.
- Final score composition and reason code generator.
- Unit tests for all exclusion and formula logic.

Acceptance:
- Excluded parcels never appear in ranked result set.
- Deterministic scores for fixed fixtures.

## Phase 4: Dashboard and Opportunity Detail UI (Complete)
Deliverables:
- Opportunities list page with filters/sort.
- Opportunity detail page with score and reason breakdown.
- Always-visible disclaimer banner.
- Feedback controls (thumbs up/down).

Acceptance:
- User can browse ranked opportunities and inspect rationale.
- Feedback persists via API call.

## Phase 5: Scheduler + Digest + Retention (Complete)
Deliverables:
- Daily scheduler job.
- Digest generator (top 20, county diversity target).
- Retention purge logic for records older than 24 months.
- Run log dashboard page.

Acceptance:
- Scheduled and manual runs both succeed.
- Daily digest is generated and retrievable.
- Retention job purges stale data only.

## Phase 6: Hunt County Scraper Vertical Slice (Complete)
Deliverables:
- Introduce scraper-first provider interfaces:
  - `CountyAuctionScraperProvider` (fetch + parse)
  - `CountyScrapeResult` (records + warnings + provenance stats)
- Implement Hunt County, TX adapter for official auction source(s) with deterministic parsing.
- Map Hunt County scraper output into canonical candidate model and existing scoring pipeline.
- Persist provenance metadata (source URL/file, fetched timestamp, parser version/checksum).
- Add tests:
  - Hunt parser fixtures
  - pipeline degraded/success behavior with scraper input
  - dedupe/idempotency for repeated scrape snapshots

Acceptance:
- Live run succeeds using Hunt County scraper without requiring RapidAPI credentials.
- Runs/settings surfaces scraper diagnostics (attempted fetches, parse failures, coverage).
- Empty/unavailable source triggers `degraded` with clear provider events, not silent failure.

## Phase 7: Scraper Data Quality and Compliance Hardening (Complete)
Deliverables:
- Scraper guardrails: request throttling, retry/backoff, and source allowlist checks.
- Parser contract tests for schema drift handling and failure classification.
- Local raw snapshot retention rules for reproducible parsing/audit.
- Auction-specific normalization checks (parcel key quality, price/acres sanity bounds).
- Two-tier Hunt pull validation workflow (fixture gate + live smoke check) with JSON evidence reports.

Acceptance:
- Source schema changes are detected and surfaced as actionable degraded errors.
- Re-running the same snapshot produces deterministic normalized outputs.
- Run logs include county-level scrape coverage and parse quality metrics.
- Hunt validation passes when at least one Hunt record is accepted and artifacts are persisted.
- Live Hunt validation passes when at least one Hunt row is parsed and artifacts are persisted (accepted-count can be zero due filters and is warning-pass).

## Phase 8: RapidAPI Deprecation and Removal (Complete)
Deliverables:
- Remove RapidAPI listing/metrics adapters from active pipeline wiring.
- Remove `rapidapi_*`/listing-scan config from settings response and frontend provider panel.
- Remove RapidAPI-specific environment variables from `.env.example` and docs.
- Delete or archive RapidAPI provider modules/tests after scraper parity is validated.

Acceptance:
- End-to-end app run works with no RapidAPI configuration present.
- Test suite has no required RapidAPI dependencies.
- Docs and code contracts no longer advertise RapidAPI as supported live ingestion.

## Phase 9: County Expansion Framework (In Progress)
### 9.1 Source Catalog and County Registry
Deliverables:
- Add file-backed source catalog (`backend/config/county_sources.yaml`) as source-of-truth for county bindings.
- Registry loader validates parser template keys, URL presence, and host allowlists.
- Backward compatibility mode falls back to legacy Hunt env wiring if catalog is missing.

Acceptance:
- `LANDORAMA_SOURCE_CATALOG_PATH` resolves to a valid catalog in normal operation.
- Invalid catalog rows fail fast with actionable errors.
- Legacy fallback mode emits explicit warning diagnostics.

### 9.2 Template Parser Layer
Deliverables:
- Introduce parser template registry (`csv_taxsale_v1`, `pdf_taxsale_v1`, `html_table_taxsale_v1` scaffold).
- Refactor county scraper orchestration to route by parser template key instead of hardcoded county parser logic.
- Preserve deterministic dedupe and provenance parser versioning.

Acceptance:
- Parser template tests cover CSV/PDF success and schema mismatch failure classification.
- New counties can be added by catalog entries without pipeline rewrites.

### 9.3 Multi-County Orchestration and Coverage Diagnostics
Deliverables:
- Execute enabled counties + sources in one scraper provider run.
- Emit county-level diagnostics (records found/accepted/rejected and price summary stats).
- Extend settings API with county coverage array and failure counts.

Acceptance:
- One county failure does not fail the whole run if others succeed.
- All-county failure marks scraper provider as failed.
- Runs/settings surfaces county coverage health clearly.

### 9.4 Rollout Pack: Hunt + 5 Counties
Deliverables:
- Onboard catalog entries for Hunt, Collin, Delta, Fannin, Hopkins, and Rains.
- Add fixture replay coverage for each rollout county.
- Produce live validation evidence reports for rollout counties.

Acceptance:
- At least 4 of 6 rollout counties pass live validation with persisted artifacts.
- Fixture validation enforces `accepted >= 1` per tested county.
- Digest reflects multi-county inventory where available.

## Phase 10: Hardening and Release Candidate
Deliverables:
- Integration tests for end-to-end runs using scraper fixtures and mock fallback.
- Basic UI test coverage for scraper diagnostics and source provenance display.
- Operator runbook for scraper troubleshooting and county onboarding checklist.

Acceptance:
- One-command local startup documented and verified.
- Full daily pipeline tested with Hunt County live scraper and deterministic fixture replay.
- No unresolved critical defects.
