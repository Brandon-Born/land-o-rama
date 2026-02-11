# Architecture (V1)

## Overview
Land-O-Rama is a local-first web application with:
- FastAPI backend for ingestion, scoring, and APIs.
- React frontend for discovery and review workflows.
- SQLite for persisted listings, features, scores, and run logs.
- Daily scheduler for automated ETL + scoring + digest generation.

## High-Level Components
- `Provider Adapters`
  - Listings adapter (RapidAPI `for-sale` location scans in live mode, fixtures in mock mode).
  - Auctions adapter (CSV ingestion in live mode, mock fallback in mock mode).
  - Parcel enrichment adapter (Regrid in live mode, noop in mock mode).
  - Trend metrics adapter (RapidAPI in live mode, mock fallback in mock mode).
  - Personalization model adapter (local artifact scoring with threshold gating).
- `Normalization + Dedupe`
  - Converts source payloads into canonical entities.
  - Handles parcel key resolution and duplicate suppression.
- `Scoring Engine`
  - Applies hard exclusions.
  - Computes factor scores.
  - Produces final rank + reason codes.
- `Digest Builder`
  - Generates daily top-opportunity report with county diversity.
- `Web API`
  - Read endpoints for opportunity browsing.
  - Write endpoint for feedback.
  - Operational endpoints for runs/settings.
- `Scheduler`
  - Executes daily pipeline, nightly personalization training, and retention purge.

## Data Flow
1. Pull new listing and auction data from provider adapters.
2. Normalize records into canonical parcel-oriented schema.
3. Enrich records with parcel facts and county trend metrics.
4. Compute features and evaluate hard exclusions.
5. Score non-excluded candidates.
6. Persist opportunities and run metadata.
7. Build daily digest from top-ranked opportunities.
8. Serve results via REST API to frontend.

## Storage Model
- Local DB file: `/Users/bborn/land-o-rama/data/landorama.db`.
- Schema lifecycle managed by Alembic migrations (`alembic upgrade head`).
- WAL mode enabled for better local concurrency.
- 24-month retention policy for historical records.
- Provider raw payloads retained for audit/debug within retention window.

## Reliability Strategy
- Per-provider timeouts and retries with backoff.
- Listings live scans are paginated by location; partial page failures produce warnings and degraded runs.
- Partial-failure tolerance: mark run degraded but continue pipeline if possible.
- Explicit run status table with timestamps, counts, and error summaries.
- Idempotent daily run keyed by run date/source snapshot.

## Security Model (Local)
- API keys loaded from `.env`.
- No credentials committed to git.
- Local-only deployment in v1 (no public internet exposure required).

## Frontend Information Architecture
- Dashboard: filters, rankings, KPIs, disclaimers (list-first view).
- Opportunity detail: dedicated tab with score factors, risks, source destination link, and feedback.
- Digest history: latest + prior generated digests.
- Runs/settings: operational health and connector status (including provider diagnostics).
