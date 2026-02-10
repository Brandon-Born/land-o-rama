# Implementation Backlog (Execution Order)

This backlog is ordered and decision-complete for v1.

## Phase 1: Project Scaffold
Deliverables:
- Backend app skeleton (`FastAPI`, config, health endpoint).
- Frontend app skeleton (`React + TypeScript + Vite`).
- SQLite setup + Alembic migration baseline.
- Local run scripts and `.env.example`.

Acceptance:
- Backend and frontend boot locally.
- Health endpoint returns success.
- Initial migration creates base schema.

## Phase 2: Canonical Data Model + Mock Ingestion
Deliverables:
- Canonical tables for listings, auctions, parcels, metrics, opportunities, feedback, runs.
- Mock providers with representative fixtures.
- Normalization and dedupe pipeline.

Acceptance:
- Mock run ingests records and stores normalized entities.
- Duplicate payloads do not create duplicate parcels.

## Phase 3: Scoring Engine + Exclusions
Deliverables:
- Hard exclusion evaluator.
- Factor score computation.
- Final score composition and reason code generator.
- Unit tests for all exclusion and formula logic.

Acceptance:
- Excluded parcels never appear in ranked result set.
- Deterministic scores for fixed fixtures.

## Phase 4: Dashboard and Opportunity Detail UI
Deliverables:
- Opportunities list page with filters/sort.
- Opportunity detail page with score and reason breakdown.
- Always-visible disclaimer banner.
- Feedback controls (thumbs up/down).

Acceptance:
- User can browse ranked opportunities and inspect rationale.
- Feedback persists via API call.

## Phase 5: Scheduler + Digest + Retention
Deliverables:
- Daily scheduler job.
- Digest generator (top 20, county diversity target).
- Retention purge logic for records older than 24 months.
- Run log dashboard page.

Acceptance:
- Scheduled and manual runs both succeed.
- Daily digest is generated and retrievable.
- Retention job purges stale data only.

## Phase 6: Live Providers (Staged Enablement)
Deliverables:
- RapidAPI listings adapter.
- Regrid parcel enrichment adapter.
- Auction feed live adapter(s) where structured data is available.
- Provider health reporting and fallback behavior.

Acceptance:
- Live adapter runs ingest real records with safe error handling.
- Provider outages produce degraded status, not full crash.

## Phase 7: Feedback Personalization
Deliverables:
- Threshold-based retraining trigger (`>= 50` labels).
- Nightly personalization model job.
- Blend personalization into final score per spec.

Acceptance:
- Before threshold: base model only.
- After threshold: blended score active and traceable.

## Phase 8: Hardening and Release Candidate
Deliverables:
- Integration tests for end-to-end run.
- Basic UI test coverage for critical flows.
- Seed data script.
- Operator runbook and troubleshooting notes.

Acceptance:
- One-command local startup documented and verified.
- Full daily pipeline tested with mock and at least one live provider.
- No unresolved critical defects.
