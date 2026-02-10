# Land-O-Rama

Local-first investment research app for finding low-cost vacant land listings with strong 5-year upside potential.

## Mission
- Identify Texas vacant land opportunities priced at or below `$5,000`.
- Filter out high-risk parcels using strict exclusions.
- Rank remaining candidates with explainable, factor-based scoring.
- Provide a web dashboard and daily digest on a local MacBook Air setup.

## V1 Product Decisions (Locked)
- Geography: Texas only.
- Inventory: Listings + auctions.
- Focus: Buildable residential resale potential.
- Delivery: Web dashboard + daily digest.
- Data lifecycle: 24 months local history in SQLite.
- Explainability: Score breakdown + reason codes.
- Risk handling: Strict hard exclusions.

## Planned Stack
- Backend: FastAPI + SQLAlchemy + Alembic + APScheduler.
- Frontend: React + TypeScript + Vite.
- Database: SQLite (local file, WAL mode).

## Documentation Index
- `/AGENTS.md`: Repo operating guide for future agents.
- `/docs/PROJECT_SPEC.md`: Product scope and acceptance criteria.
- `/docs/ARCHITECTURE.md`: System design and data flow.
- `/docs/SCORING_SPEC.md`: Ranking algorithm and exclusion rules.
- `/docs/API_SPEC.md`: Backend API contracts.
- `/docs/IMPLEMENTATION_BACKLOG.md`: Ordered build phases and tasks.

## Immediate Next Step
Start Phase 1 from `/docs/IMPLEMENTATION_BACKLOG.md` to scaffold backend/frontend and database migrations.
