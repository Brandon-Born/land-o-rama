# Land-O-Rama

Local-first investment research app for finding low-cost vacant land listings with strong 5-year upside potential.

## Current Status
Implemented MVP vertical slice:
- FastAPI backend with SQLite persistence.
- Mock listings + auction ingestion pipeline.
- Strict exclusion and explainable scoring engine.
- Daily digest and run logging.
- React web UI for dashboard, detail review, digest, and runs.

## V1 Product Decisions (Locked)
- Geography: Texas only.
- Inventory: Listings + auctions.
- Focus: Buildable residential resale potential.
- Delivery: Web dashboard + daily digest.
- Data lifecycle: 24 months local history in SQLite.
- Explainability: Score breakdown + reason codes.
- Risk handling: Strict hard exclusions.

## Stack
- Backend: FastAPI + SQLAlchemy + APScheduler.
- Frontend: React + TypeScript + Vite.
- Database: SQLite (local file, WAL mode).

## Quick Start
### 1) Backend
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

### 2) Frontend
```bash
cd /Users/bborn/land-o-rama/frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

## Database Migrations
From `/Users/bborn/land-o-rama`:
- `make db-upgrade`
- `make db-revision MSG="your migration message"`

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
