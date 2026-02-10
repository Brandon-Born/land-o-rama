# Project Spec (V1)

## Goal
Build a local app that surfaces potentially undervalued Texas land opportunities under `$5,000` with a 5-year resale upside thesis.

## Primary User
- Single operator/investor running the app on a MacBook Air.

## Core Jobs-to-be-Done
- Aggregate low-price land opportunities from listings and auctions.
- Analyze county-level growth and parcel-level feasibility signals.
- Exclude high-risk opportunities that fail minimum quality bars.
- Rank candidates and explain why each could appreciate.
- Review top daily opportunities via dashboard and digest.

## Scope
In scope:
- Texas-only market coverage.
- Listings + auctions ingestion.
- Daily refresh schedule.
- Local SQLite persistence (24 months).
- Explainable ranking output with reason codes.
- Manual thumbs up/down feedback loop.

Out of scope:
- Automated transaction execution.
- Legal/tax advice.
- Nationwide rollout.
- Multi-user accounts or cloud deployment.

## Success Criteria
- App produces a ranked opportunity list every day.
- All shown opportunities include score breakdown and rationale.
- Hard-risk parcels are excluded from display.
- Daily digest reliably surfaces top 20 opportunities.
- User can provide feedback that is stored for model tuning.

## Non-Functional Requirements
- Fully local operation once configured.
- Reasonable runtime on consumer MacBook Air hardware.
- Fault-tolerant ETL logging (failed provider calls do not crash app).
- Deterministic scoring outputs for identical input snapshots.

## Compliance and UX Safeguards
- Always-visible disclaimer that output is informational, not investment advice.
- Display data freshness timestamps and source coverage notes.
