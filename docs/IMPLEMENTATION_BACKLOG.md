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

## Phase 7: Scraper Data Quality and Compliance Hardening (In Progress)
Deliverables:
- Scraper guardrails: request throttling, retry/backoff, and source allowlist checks.
- Parser contract tests for schema drift handling and failure classification.
- Local raw snapshot retention rules for reproducible parsing/audit.
- Auction-specific normalization checks (parcel key quality, price/acres sanity bounds).

Acceptance:
- Source schema changes are detected and surfaced as actionable degraded errors.
- Re-running the same snapshot produces deterministic normalized outputs.
- Run logs include county-level scrape coverage and parse quality metrics.

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
Deliverables:
- County registry configuration (enabled counties, source endpoints, parser bindings).
- Add at least 2 additional Texas county scraper adapters after Hunt County stabilization.
- Update scheduler to execute enabled county scrapes with per-county run diagnostics.

Acceptance:
- County onboarding is config-driven (no pipeline rewrites per new county).
- Per-county failures degrade gracefully while other counties continue processing.
- Digest reflects county diversity from enabled scraper coverage.

## Phase 10: Hardening and Release Candidate
Deliverables:
- Integration tests for end-to-end runs using scraper fixtures and mock fallback.
- Basic UI test coverage for scraper diagnostics and source provenance display.
- Operator runbook for scraper troubleshooting and county onboarding checklist.

Acceptance:
- One-command local startup documented and verified.
- Full daily pipeline tested with Hunt County live scraper and deterministic fixture replay.
- No unresolved critical defects.
