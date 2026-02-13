# Agent Operating Guide

This file defines how future agents should continue implementation in this repo.

## First Read Order
1. `/README.md`
2. `/docs/PROJECT_SPEC.md`
3. `/docs/ARCHITECTURE.md`
4. `/docs/SCORING_SPEC.md`
5. `/docs/API_SPEC.md`
6. `/docs/IMPLEMENTATION_BACKLOG.md`
7. `/docs/WORK_LOG.md`

## Ground Rules
- Treat documentation above as source-of-truth unless user explicitly overrides.
- Do not redesign core product decisions without updating the matching docs.
- Keep v1 scoped to local single-user operation on macOS.
- Preserve strict exclusion logic for high-risk parcels.
- Keep explainability mandatory for surfaced opportunities.
- Primary live data source is county auction scraping (pilot county: Hunt County, TX).
- RapidAPI listings/metrics integrations are deprecated and should not receive new feature work.

## Execution Priority
1. Implement smallest vertical slice that runs locally end-to-end.
2. Prefer deterministic behavior over speculative ML complexity.
3. Keep provider integrations pluggable via adapter interfaces.
4. Ship mock-mode first, then live providers.
5. Prioritize Hunt County scraper ingestion and deprecation/removal of RapidAPI paths.

## Required Engineering Practices
- Use typed models for API payloads and DB entities.
- Add tests for scoring/exclusion logic before tuning weights.
- Log all ETL runs with status, counts, and errors.
- Keep secrets in `.env`; never commit credentials.
- Store local database in `/data` and keep it gitignored.

## Change Control
If changing any of these, update docs in the same PR:
- Score weights or feature definitions.
- Hard exclusion criteria.
- Public API endpoints or response shapes.
- Data retention period.
- Digest composition rules.

## Done Criteria (Per Task)
- Code compiles/runs locally.
- Tests added or updated for behavior changes.
- Docs updated where contracts changed.
- Manual verification steps documented in task notes or PR description.

## Completion Log Protocol (Mandatory)
- Every time a task is considered complete, append an entry to `/docs/WORK_LOG.md` in the same commit.
- Do not overwrite history; append newest entries at the bottom.
- Each entry must include:
  - Date (YYYY-MM-DD)
  - Task summary
  - Files changed (paths)
  - Validation performed (tests/checks/manual)
  - Next recommended tasks
