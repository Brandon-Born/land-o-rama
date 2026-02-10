backend-install:
	cd backend && /opt/homebrew/bin/python3.13 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

backend-dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && . .venv/bin/activate && pytest -q

test-api:
	cd backend && . .venv/bin/activate && pytest -q tests/test_api_*.py

db-upgrade:
	cd backend && . .venv/bin/activate && alembic upgrade head

db-revision:
	cd backend && . .venv/bin/activate && alembic revision -m "$(MSG)"
