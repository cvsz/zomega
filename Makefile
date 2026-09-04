.PHONY: help install venv init migrate db-check serve worker dev test test-integration test-all lint lint-fix format typecheck check validate verify compose-up compose-down compose-logs compose-ps backup restore restore-verify gpg-status clean

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

help:
	@echo "zomega Production Platform - Makefile Commands"
	@echo "=============================================="
	@echo "Setup & Environment:"
	@echo "  make install           - Run install.sh and configure virtual environment"
	@echo "  make venv              - Create local Python virtual environment"
	@echo ""
	@echo "Database & Migrations:"
	@echo "  make init              - Run database migrations to head (alembic upgrade head)"
	@echo "  make migrate           - Generate migration revision (usage: make migrate msg=\"add table\")"
	@echo "  make db-check          - Verify database connectivity and schema readiness"
	@echo ""
	@echo "Run & Services:"
	@echo "  make serve             - Run production API server ($(PYTHON) -m zomega serve)"
	@echo "  make worker            - Run background ARQ worker (arq zomega.jobs.WorkerSettings)"
	@echo "  make dev               - Run development API server with hot-reload"
	@echo ""
	@echo "Testing & Verification:"
	@echo "  make test              - Run standard unit test suite"
	@echo "  make test-integration  - Run integration tests (requires Postgres & Redis)"
	@echo "  make test-all          - Run both unit and integration tests"
	@echo "  make validate          - Run full local validation (compileall, lint, typecheck, test)"
	@echo "  make verify            - Run production release verification gate (./verify.sh)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run ruff linter across zomega and tests"
	@echo "  make lint-fix          - Run ruff with automated fixes"
	@echo "  make format            - Run ruff code formatter"
	@echo "  make typecheck         - Run mypy type analysis on core modules"
	@echo "  make check             - Run lint, typecheck, and unit tests"
	@echo ""
	@echo "Docker & Orchestration:"
	@echo "  make compose-up        - Start services in background (docker compose up -d)"
	@echo "  make compose-down      - Stop and tear down docker compose services"
	@echo "  make compose-logs      - Follow docker compose logs"
	@echo "  make compose-ps        - View running compose services"
	@echo ""
	@echo "Operations & Disaster Recovery:"
	@echo "  make backup            - Execute database backup (./backup.sh)"
	@echo "  make restore           - Restore database (usage: make restore src=backups/file.dump)"
	@echo "  make restore-verify    - Run automated restore verification drill (./restore-verify.sh)"
	@echo ""
	@echo "Git & Clean:"
	@echo "  make gpg-status        - Show GPG agent and commit signing status"
	@echo "  make clean             - Clean build artifacts, pyc, and test caches"

install:
	./install.sh

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

init:
	alembic upgrade head

migrate:
	alembic revision --autogenerate -m "$(msg)"

db-check:
	$(PYTHON) -m zomega db-check

serve:
	$(PYTHON) -m zomega serve

worker:
	arq zomega.jobs.WorkerSettings

dev:
	uvicorn zomega.api:app --reload --host 0.0.0.0 --port 8000

test:
	$(PYTHON) -m unittest discover -s tests -v

test-integration:
	zomega_INTEGRATION=1 RUN_INTEGRATION_TESTS=1 $(PYTHON) -m unittest discover -s tests -v

test-all: test test-integration

lint:
	ruff check zomega tests

lint-fix:
	ruff check --fix zomega tests

format:
	ruff format zomega tests

typecheck:
	mypy zomega/security.py zomega/audit.py zomega/key_service.py zomega/commercial.py zomega/registry.py zomega/marketplace.py

check: lint typecheck test

validate:
	$(PYTHON) -m compileall -q zomega tests
	ruff check zomega tests
	mypy zomega/security.py zomega/audit.py zomega/key_service.py zomega/commercial.py zomega/registry.py zomega/marketplace.py
	$(PYTHON) -m unittest discover -s tests -v

verify:
	./verify.sh

compose-up:
	docker compose up -d

compose-down:
	docker compose down

compose-logs:
	docker compose logs -f

compose-ps:
	docker compose ps

backup:
	./backup.sh

restore:
	@if [ -z "$(src)" ]; then echo "Error: specify dump file with src=backups/..."; exit 1; fi
	./restore.sh "$(src)"

restore-verify:
	./restore-verify.sh

gpg-status:
	git gpg-agents

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
