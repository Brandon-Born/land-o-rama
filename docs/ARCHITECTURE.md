# Architecture (V1)

## Overview
Land-O-Rama is a local-first web application with:
- FastAPI backend for ingestion, scoring, and APIs.
- React frontend for discovery and review workflows.
- SQLite for persisted listings, features, scores, and run logs.
- Daily scheduler for automated ETL + scoring + digest generation.

## High-Level Components
- `Provider Adapters`
  - County auction scraper adapter (primary live source; Hunt County first).
  - Auctions CSV adapter (transitional ingest path and parser fallback).
  - Parcel enrichment adapter (Regrid in live mode, noop in mock mode).
  - Trend metrics adapter (local/mock metrics now; pluggable replacement sources later).
  - Personalization model adapter (local artifact scoring with threshold gating).
- `Scraper Orchestration`
  - County source registry (enabled counties, URLs, parser strategy).
  - Fetch runner (HTTP/download, robots/terms compliance checks, retries).
  - Parse + normalize stage (HTML/CSV/PDF extracts into canonical auction records).
  - Provenance capture (source URL/file, fetch time, parser version, checksum).
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

## Template-Driven County Ingestion
- `Source Catalog`
  - File-backed county/source registry (`backend/config/county_sources.yaml`) defines county bindings, parser templates, source URLs, and allowlists.
  - Runtime filters enabled entries by `LANDORAMA_SCRAPER_TARGET_COUNTIES`.
  - Backward compatibility mode falls back to legacy Hunt env settings when the catalog file is unavailable.
- `Parser Templates`
  - `csv_taxsale_v1`: alias-aware CSV parser for tax sale exports.
  - `pdf_taxsale_v1`: line-block PDF parser for public resale lists with explicit auction-entry-price extraction when labeled and separate market-value capture for explainability.
  - `lgbs_property_sales_v1`: JSON parser for LGBS property-sales payloads with county filtering and minimum-bid/market-value fallback handling.
  - `html_table_taxsale_v1`: scaffolded template for future table-based county pages.
- `County Routing`
  - Scraper orchestration iterates enabled counties and all configured sources per county.
  - Parser selection is source-template driven (`parser_template_key`) instead of county hardcoding.
  - Dedupe identity remains `(state, parcel_key, external_id)` across all counties.
- `Coverage Metrics`
  - Provenance persists per source and county in `scrape_artifacts`.
  - Settings endpoint surfaces county coverage diagnostics (records found/accepted/rejected and price summaries).
  - Live validation reports include county-level pass/warn/fail outcomes and source coverage.
  - Runtime supports split caps: ingestion cap for pipeline acceptance and a lower default dashboard cap for user-facing opportunity filtering.

## Data Flow
1. Fetch county auction source pages/files from scraper adapters (Hunt County first).
2. Parse and normalize records into canonical parcel-oriented schema.
3. Capture source provenance metadata for each normalized record.
4. Enrich records with parcel facts and county trend metrics.
5. Compute features and evaluate hard exclusions.
6. Score non-excluded candidates.
7. Persist opportunities and run metadata.
8. Build daily digest from top-ranked opportunities.
9. Serve results via REST API to frontend.

## Storage Model
- Local DB file: `/Users/bborn/land-o-rama/data/landorama.db`.
- Schema lifecycle managed by Alembic migrations (`alembic upgrade head`).
- WAL mode enabled for better local concurrency.
- 24-month retention policy for historical records.
- Provider raw payloads retained for audit/debug within retention window.

## Reliability Strategy
- Per-provider timeouts and retries with backoff.
- Scraper fetch + parse stages emit per-source diagnostics (fetch failures, parse failures, schema mismatches).
- Scraper parser versioning and provenance checks support deterministic reprocessing.
- Hunt parser coverage includes CSV (`hunt_csv_v1`) and resale PDF (`hunt_pdf_v1`) with a shared canonical candidate mapping.
- Hunt pull validation emits JSON evidence reports and cross-checks `sync_runs`, `provider_run_events`, and `scrape_artifacts`.
- Live validation separates source availability health (`records_found`) from business yield health (`records_accepted`) and applies a streak-based yield gate for persistent zero-accepted runs.
- If all configured Hunt sources fail for a run (`attempted_sources > 0` and `successful_sources == 0`), scraper provider health is `failed`.
- Partial-failure tolerance: mark run degraded but continue pipeline if possible.
- Explicit run status table with timestamps, counts, and error summaries.
- Idempotent daily run keyed by run date/source snapshot.

## Security Model (Local)
- API keys loaded from `.env` only for optional non-primary enrichers.
- No credentials committed to git.
- Local-only deployment in v1 (no public internet exposure required).
- Respect source access constraints and retain only permitted local source snapshots.

## Frontend Information Architecture
- Dashboard: filters, rankings, KPIs, disclaimers (list-first view).
- Opportunity detail: dedicated tab with score factors, risks, source destination link, and feedback.
- Digest history: latest + prior generated digests.
- Runs/settings: operational health and scraper diagnostics (county coverage, parser status, degraded causes).
