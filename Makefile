.PHONY: help build up down test test-unit test-integration lint typecheck migrate seed logs weather-history

DOCKER_COMPOSE = docker compose -f docker/docker-compose.yml
DOCKER_COMPOSE_LOCAL_LLM = docker compose -f docker/docker-compose.yml --profile local-llm

# Runtime and test commands in this repository are Docker-only.

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Docker ──────────────────────────────────────────────────────────────────

build:  ## Build all Docker images
	$(DOCKER_COMPOSE) build

up:  ## Start all services (detached)
	$(DOCKER_COMPOSE) up -d db redis

up-all:  ## Start all services including app, worker, and ollama
	$(DOCKER_COMPOSE_LOCAL_LLM) up -d

down:  ## Stop and remove all containers
	$(DOCKER_COMPOSE) down

logs:  ## Tail logs for all services
	$(DOCKER_COMPOSE) logs -f

# ── Database ─────────────────────────────────────────────────────────────────

migrate:  ## Run Alembic migrations
	$(DOCKER_COMPOSE) run --rm app alembic upgrade head

migrate-rollback:  ## Rollback last migration
	$(DOCKER_COMPOSE) run --rm app alembic downgrade -1

seed:  ## Load Alabama baseline schedule seed data
	$(DOCKER_COMPOSE) exec db psql -U aisprinkler -d aisprinkler \
		-f /dev/stdin < config/seeds/alabama_baseline_schedule.sql

# ── Testing ──────────────────────────────────────────────────────────────────

test:  ## Run the full test suite in Docker
	$(DOCKER_COMPOSE) run --build --rm test

test-unit:  ## Run only unit tests in Docker
	$(DOCKER_COMPOSE) run --build --rm test pytest tests/unit -v --tb=short

test-integration:  ## Run only integration tests in Docker
	$(DOCKER_COMPOSE) run --build --rm test pytest tests/integration -v --tb=short

test-cov:  ## Run tests with HTML coverage report in Docker
	$(DOCKER_COMPOSE) run --build --rm test pytest --cov=src/aisprinkler --cov-report=html:htmlcov
	@echo "Coverage report: htmlcov/index.html"

# ── Quality ──────────────────────────────────────────────────────────────────

lint:  ## Run ruff linter
	ruff check src tests scripts

lint-fix:  ## Auto-fix ruff lint issues
	ruff check --fix src tests scripts

typecheck:  ## Run mypy type checker
	mypy src

fmt:  ## Format code with ruff formatter
	ruff format src tests scripts

# ── Trigger Scripts ───────────────────────────────────────────────────────────

trigger-daily:  ## Trigger daily adjustment run manually in Docker
	$(DOCKER_COMPOSE) run --rm -v "$$(pwd)/scripts:/app/scripts:ro" app python /app/scripts/trigger_daily_adjustment.py

retry-run:  ## Retry a failed run in Docker (ARGS: RUN_ID=<uuid>)
	$(DOCKER_COMPOSE) run --rm -v "$$(pwd)/scripts:/app/scripts:ro" app python /app/scripts/retry_failed_run.py $(RUN_ID)

process-reviews:  ## Process pending manual review queue in Docker
	$(DOCKER_COMPOSE) run --rm -v "$$(pwd)/scripts:/app/scripts:ro" app python /app/scripts/process_manual_reviews.py

weather-history:  ## Backfill weather history into DB (HISTORY_DAYS env controls window)
	$(DOCKER_COMPOSE) run --rm -v "$$(pwd)/scripts:/app/scripts:ro" app python /app/scripts/weather_spanishfort.py

baseline-history:  ## Create dated baseline history rows (BASELINE_HISTORY_DAYS env controls window)
	$(DOCKER_COMPOSE) run --rm -v "$$(pwd)/scripts:/app/scripts:ro" app python /app/scripts/create_baseline_last30d.py

replay-adjustments:  ## Replay historical adjustments (ADJUST_HISTORY_DAYS env controls window)
	$(DOCKER_COMPOSE_LOCAL_LLM) run --rm -v "$$(pwd)/scripts:/app/scripts:ro" -e AGENT_MODE=langchain app python /app/scripts/adjust_schedule_last30d.py

# ── Dev ───────────────────────────────────────────────────────────────────────

install:  ## Install Python deps in editable mode with dev extras
	pip install -e ".[dev]"

dev:  ## Start API service in Docker
	$(DOCKER_COMPOSE) up -d app

worker:  ## Start Celery worker service in Docker
	$(DOCKER_COMPOSE) up -d worker
