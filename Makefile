.PHONY: help setup dev test lint typecheck format seed reset preflight

help:
	@echo "OrgMind Monorepo Commands:"
	@echo "  make setup      - Install core package in editable mode with dev dependencies"
	@echo "  make dev        - Launch legacy Streamlit UI for development"
	@echo "  make test       - Run unit tests and smoke suite"
	@echo "  make lint       - Run ruff code linter"
	@echo "  make typecheck  - Run mypy static type checker"
	@echo "  make format     - Run ruff format and code fixes"
	@echo "  make seed       - Ingest structured and unstructured base datasets"
	@echo "  make reset      - Reset FalkorDB graph to clean baseline"
	@echo "  make preflight  - Run end-to-end subsystem verification"

setup:
	python -m pip install --upgrade pip
	python -m pip install -e "packages/core[dev]"
	python -m pip install -e ".[api,dev]"

dev:
	@echo "Starting fullstack development environment..."
	@echo "API: make dev-api"
	@echo "Web: make dev-web"
	@echo "Worker: make dev-worker"

dev-api:
	python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	cd apps/web && npm run dev

dev-worker:
	python -m apps.worker.main

dev-legacy:
	python -m streamlit run apps/legacy-streamlit/streamlit_app.py --server.port 8501

test:
	python -m pytest tests/ -v
	python scripts/smoke_test.py

test-eval:
	python tests/run_eval.py --limit 10

lint:
	python -m ruff check packages/core apps scripts tests

typecheck:
	python -m mypy packages/core

format:
	python -m ruff format packages/core apps scripts tests
	python -m ruff check --fix packages/core apps scripts tests

seed:
	python packages/core/orgmind/ingest_structured.py
	python packages/core/orgmind/ingest_unstructured.py

reset:
	python scripts/reset_demo.py

backup:
	python scripts/backup_restore.py backup --graph northwind_labs --file data/backups/graph_backup.json

restore:
	python scripts/backup_restore.py restore --graph northwind_labs --file data/backups/graph_backup.json

compose-up:
	docker compose --profile fullstack up --build

compose-down:
	docker compose --profile fullstack down

preflight:
	python scripts/preflight.py

