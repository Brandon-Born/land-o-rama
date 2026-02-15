# Land-O-Rama

Local-first investment research app for finding low-cost vacant land opportunities with strong 5-year upside potential.

## Current Status
Implemented MVP vertical slice:
- FastAPI backend with SQLite persistence.
- Live auction CSV ingestion pipeline with strict exclusion and explainable scoring.
- Live Hunt County, TX scraper-first ingestion path (download-first) with provenance capture.
- Strict exclusion and explainable scoring engine.
- Daily digest and run logging.
- Threshold-based personalization training (`>= 50` feedback labels) with nightly retrain job.
- React web UI for dashboard, detail review, digest, and runs.

## V1 Product Decisions (Locked)
- Geography: Texas county-by-county, starting with Hunt County, TX.
- Inventory: County auction data as primary source.
- Focus: Buildable residential resale potential.
- Delivery: Web dashboard + daily digest.
- Data lifecycle: 24 months local history in SQLite.
- Explainability: Score breakdown + reason codes.
- Risk handling: Strict hard exclusions.

## Data Source Pivot (Effective 2026-02-13)
- Primary source direction: scrape county land/tax auction sources directly.
- Initial live coverage target: Hunt County, Texas.
- RapidAPI functionality has been removed from runtime and settings contracts.
- County registry scaffold exists for adding additional Texas counties after Hunt stabilization.

## Stack
- Backend: FastAPI + SQLAlchemy + APScheduler.
- Frontend: React + TypeScript + Vite.
- Database: SQLite (local file, WAL mode).

## Quick Start
### 1) One Command (Recommended)
From `/Users/bborn/land-o-rama`:
```bash
make dev
```

What `make dev` does:
- Creates backend virtualenv on first run (Python `3.13`).
- Installs backend/frontend dependencies if missing.
- Creates `backend/.env` from `.env.example` if missing.
- Applies Alembic migrations.
- Starts backend (`:8000`) and frontend (`:5173`) together.

Stop both services with `Ctrl+C`.

### 2) Manual Backend
```bash
cd /Users/bborn/land-o-rama/backend
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Note: Python `3.13` is required for the current dependency set. Python `3.14` will fail when building `pydantic-core`.

If you previously ran the app before Alembic adoption, recreate your local DB for clean parity:
```bash
rm -f /Users/bborn/land-o-rama/data/landorama.db*
cd /Users/bborn/land-o-rama/backend
source .venv/bin/activate
alembic upgrade head
```

### 3) Manual Frontend
```bash
cd /Users/bborn/land-o-rama/frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

Frontend tests:
```bash
cd /Users/bborn/land-o-rama/frontend
npm run test
```

## County Auction Ingestion Mode (Primary)
Drop county auction files into your configured directory (default `/Users/bborn/land-o-rama/data/auction_feeds`).

Supported canonical columns:
- `auction_id`, `parcel_key`, `county`, `state`, `price`, `acreage`, `latitude`, `longitude`
- `zoning`, `legal_access`, `utilities_hint`, `flood_risk_level`, `wetland_risk_level`
- `road_distance_miles`, `days_on_market`, `price_per_acre`

Common aliases are accepted (`id`, `apn`, `winning_bid`, `acres`, `lat`, `lon`, etc.). Invalid rows are skipped and surfaced as degraded provider events.

## Scraper Runtime Mode (Primary)
- Set `LANDORAMA_AUCTION_SOURCE_MODE=scraper`.
- Set `LANDORAMA_SCRAPER_TARGET_COUNTIES` to one or more counties (comma-separated).
- Set `LANDORAMA_SOURCE_CATALOG_PATH` to your county source catalog (default `backend/config/county_sources.yaml`).
- Parser templates now route by source binding (`csv_taxsale_v1`, `pdf_taxsale_v1`, `lgbs_property_sales_v1`, `html_table_taxsale_v1` scaffold).
- Recommended public-source mesh uses county/public resale publishers (no RapidAPI dependency).
- Hunt default source mesh now prefers LGBS property-sales JSON and keeps PBFCM resale PDF as fallback.
- Two-tier pricing controls:
  - `LANDORAMA_INGESTION_PRICE_CAP` controls pipeline acceptance ceiling (default `15000`).
  - `LANDORAMA_PRICE_CAP` remains the user-facing dashboard default cap (`5000`).
- Runtime behavior: no-new-data days are marked `degraded` and prior successful opportunities remain the active dashboard data source.

## Database Migrations
From `/Users/bborn/land-o-rama`:
- `make db-upgrade`
- `make db-revision MSG="your migration message"`

## Hunt Pull Validation
Two-tier validation workflow for Hunt County scraper ingestion:
- Fixture validation (deterministic, CI-safe):
  - `make validate-hunt-fixture`
- Live validation (operational smoke check):
  - `make validate-hunt-live`

## Multi-County Validation
- Fixture validation (deterministic, all enabled/selected counties):
  - `cd backend && .venv/bin/python scripts/validate_county_pull.py --mode fixture`
- Live validation (operational smoke check):
  - `cd backend && .venv/bin/python scripts/validate_county_pull.py --mode live`
- Optional county filter:
  - `--counties hunt,collin,delta`
- Hunt-only validator remains available as a temporary compatibility alias and is deprecated.

Direct script usage:
- `cd backend && .venv/bin/python scripts/validate_hunt_pull.py --mode fixture`
- `cd backend && .venv/bin/python scripts/validate_hunt_pull.py --mode live`

Validation report output:
- Default path: `/Users/bborn/projects/land-o-rama/data/validation/hunt_pull_<timestamp>.json`
- Fixture pass criteria: at least one accepted Hunt record, no scraper hard failure, and persisted Hunt scrape artifacts.
- Live pass criteria: at least one parsed Hunt record with persisted Hunt scrape artifacts and no scraper hard failure.
- Live runs with parsed rows but zero accepted rows are warning-pass (strict mode converts warnings to failure).
- Live yield gate: warning-pass converts to failure when zero accepted rows persist across consecutive live runs (`LANDORAMA_LIVE_YIELD_FAIL_STREAK`, default `3`).

## Key API Endpoints
- `GET /health`
- `GET /api/v1/opportunities`
- `GET /api/v1/opportunities/{id}`
- `POST /api/v1/opportunities/{id}/feedback`
- `GET /api/v1/digests/latest`
- `GET /api/v1/digests`
- `POST /api/v1/jobs/run-daily`
- `GET /api/v1/runs`
- `GET /api/v1/settings`
- `PUT /api/v1/settings`

## Documentation Index
- `/Users/bborn/land-o-rama/AGENTS.md`: Repo operating guide for future agents.
- `/Users/bborn/land-o-rama/docs/PROJECT_SPEC.md`: Product scope and acceptance criteria.
- `/Users/bborn/land-o-rama/docs/ARCHITECTURE.md`: System design and data flow.
- `/Users/bborn/land-o-rama/docs/SCORING_SPEC.md`: Ranking algorithm and exclusion rules.
- `/Users/bborn/land-o-rama/docs/API_SPEC.md`: Backend API contracts.
- `/Users/bborn/land-o-rama/docs/IMPLEMENTATION_BACKLOG.md`: Ordered build phases and tasks.
- `/Users/bborn/land-o-rama/docs/SOURCE_FINDINGS.md`: Source evaluation notes and ingestion decisions.
