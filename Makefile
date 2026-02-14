SHELL := /bin/bash
PYTHON_BIN ?= /opt/homebrew/bin/python3.13

.PHONY: backend-bootstrap frontend-bootstrap setup dev backend-install backend-dev frontend-install frontend-dev test test-api db-upgrade db-revision validate-hunt-fixture validate-hunt-live validate-county-fixture validate-county-live

backend-bootstrap:
	cd backend && \
		if [ ! -d .venv ]; then $(PYTHON_BIN) -m venv .venv; fi && \
		. .venv/bin/activate && \
		if [ ! -x .venv/bin/uvicorn ]; then pip install -r requirements.txt; fi && \
		if [ ! -f .env ]; then cp .env.example .env; fi && \
		alembic upgrade head

frontend-bootstrap:
	if [ ! -d frontend/node_modules ]; then cd frontend && npm install; fi

setup: backend-bootstrap frontend-bootstrap

dev: setup
	@set -eu; \
		( cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) & \
		BACK_PID=$$!; \
		( cd frontend && npm run dev ) & \
		FRONT_PID=$$!; \
		trap 'kill $$BACK_PID $$FRONT_PID 2>/dev/null || true' INT TERM EXIT; \
		wait $$BACK_PID $$FRONT_PID

backend-install:
	cd backend && $(PYTHON_BIN) -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

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

validate-hunt-fixture:
	cd backend && .venv/bin/python scripts/validate_hunt_pull.py --mode fixture

validate-hunt-live:
	cd backend && .venv/bin/python scripts/validate_hunt_pull.py --mode live

validate-county-fixture:
	cd backend && .venv/bin/python scripts/validate_county_pull.py --mode fixture

validate-county-live:
	cd backend && .venv/bin/python scripts/validate_county_pull.py --mode live
