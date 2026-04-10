# AISprinkler

![AISprinkler dashboard screenshot](docs/images/Screenshot%202026-04-02%20023637.png)

This repository contains AISprinkler documentation and implementation code for
weather-aware sprinkler schedule adjustments with full run traceability.

Execution model: runtime and tests are Docker-only.

## Docker-Only Policy

- Run the API, worker, and dependencies via Docker Compose.
- Run all test suites via Docker Compose.
- Do not run project runtime or tests with local host Python commands.

Primary commands:

macOS/Linux (`make`):

- `make up-all` (start services)
- `make test` (all tests)
- `make test-unit` (unit tests in Docker)
- `make test-integration` (integration tests in Docker)
- `make test-cov` (coverage in Docker)

`make up-all` now starts the `local-llm` profile as well, so Ollama is included.

## Running Python Scripts in Docker (Current Image Layout)

Current `app` image layout includes `/app/src` and `/app/config`, but does not copy
the repository `scripts/` folder into the container filesystem.

For script execution, bind-mount the local scripts directory:

- macOS/Linux:

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	app python /app/scripts/<script_name>.py
```

- Windows PowerShell:

```powershell
docker compose -f docker/docker-compose.yml run --rm `
	-v "${PWD}/scripts:/app/scripts:ro" `
	app python /app/scripts/<script_name>.py
```

Examples for all current scripts:

- Trigger daily adjustment:

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	app python /app/scripts/trigger_daily_adjustment.py
```

- Retry failed run (pass run id argument):

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	app python /app/scripts/retry_failed_run.py <run_id>
```

- Process manual reviews:

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	app python /app/scripts/process_manual_reviews.py
```

- Pull weather history:

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	app python /app/scripts/weather_spanishfort.py
```

- Create 30-day baseline history:

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	app python /app/scripts/create_baseline_last30d.py
```

- Replay adjustments for last 30 days:

```bash
docker compose -f docker/docker-compose.yml run --rm \
	-v "$PWD/scripts:/app/scripts:ro" \
	-e AGENT_MODE=langchain \
	app python /app/scripts/adjust_schedule_last30d.py
```

Windows PowerShell (`docker compose`):

- `docker compose -f docker/docker-compose.yml up -d` (start services)
- `docker compose -f docker/docker-compose.yml run --build --rm test` (all tests)
- `docker compose -f docker/docker-compose.yml run --build --rm test pytest tests/unit -v --tb=short` (unit tests in Docker)
- `docker compose -f docker/docker-compose.yml run --build --rm test pytest tests/integration -v --tb=short` (integration tests in Docker)
- `docker compose -f docker/docker-compose.yml run --build --rm test pytest --cov=src/aisprinkler --cov-report=html:htmlcov` (coverage in Docker)

Optional local LLM via Ollama (Docker profile):

- `docker compose -f docker/docker-compose.yml --profile local-llm up -d ollama` (start Ollama service manually when needed)
- Set `AGENT_MODE=langchain`, `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://ollama:11434` in `.env`
- Pull a model once: `docker compose -f docker/docker-compose.yml --profile local-llm exec ollama ollama pull llama3.2`
- Start app/worker: `docker compose -f docker/docker-compose.yml --profile local-llm up -d app worker`

## Run All Historical Pipeline (30d)

One-shot Docker command sequence (weather pull, baseline history, then replay with LangChain):

```bash
docker compose -f docker/docker-compose.yml --profile local-llm up -d db redis ollama && \
docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/weather_spanishfort.py && \
docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/create_baseline_last30d.py && \
docker compose -f docker/docker-compose.yml --profile local-llm run --rm -v "$PWD/scripts:/app/scripts:ro" -e AGENT_MODE=langchain app python /app/scripts/adjust_schedule_last30d.py
```

Equivalent `make` flow:

```bash
make up-all
make weather-history
make baseline-history
make replay-adjustments
```

Database and cache viewers included in Docker Compose:

- PostgreSQL viewer: `http://localhost:8080`
- Redis viewer: `http://localhost:8081`

These viewers are intended for local development only.

Database bootstrap behavior:

- On API startup and before adjustment execution, the application creates managed tables if they do not exist.
- Missing columns for managed tables are added automatically.
- If no dated baseline exists, the application seeds a default device and populates both `original` and `current` baseline schedules for the next 7 days.
- If a legacy weekday-based `baseline_schedule` table exists, startup expands it into dated rows for the visible week-ahead window.
- Week-ahead schedules can be queried from `GET /api/v1/schedules?device_id=<uuid>&days=7`.

Adminer connection values:

- System: `PostgreSQL`
- Server: `db`
- Username: `aisprinkler`
- Password: `aisprinkler`
- Database: `aisprinkler`

Redis Commander is preconfigured to connect to the `redis` service with the current Compose defaults.

Production note:

- The current Docker Compose setup uses development-friendly values in the repository for local use.
- In production, database credentials, API keys, device identifiers, and any similar sensitive values must be stored in Docker secrets or an external secret manager, not committed to the repository.
- Adminer and Redis Commander should not be exposed in production unless they are explicitly secured and operationally justified.

## Project Goal

AISprinkler starts from a daily preset irrigation schedule stored in a database, then adjusts the next 24 hours using weather context:

- Rain observed in last 24 hours
- Rain forecast for next 24 hours
- Deterministic safety and policy rules
- Confidence-gated AI recommendation

## Locked v1 Decisions

- Stack target: Python + FastAPI + PostgreSQL + Redis + Celery
- Scope target: single device only
- Decision gate: auto-apply above threshold, manual review below threshold
- Weather strategy: multi-provider with fallback
- LLM strategy: configurable provider — OpenAI, Anthropic, or Ollama (local)
- Governance: internal auditability and traceability by default

## Current Implementation Snapshot

- Dated schedule persistence is implemented with immutable `original_baseline_schedule`
	and versioned `current_baseline_schedule` rows.
- Weather ingestion persists hourly data and refreshes the upcoming horizon by replacing
	future forecast rows on each pull.
- Forecast horizon supports next 7 days (hourly + daily rollups).
- LLM prompting is driven by `config/SPRINKLER_LLM_RULES.md` and guarded by
	post-parse coercion for clearly invalid/copy-like outputs.
- Grafana dashboard includes weather trends, schedule comparison, and LLM
	sent/received prompt exchange visibility.
- Historical support scripts exist for baseline backfill and replay:
	`scripts/create_baseline_last30d.py` and `scripts/adjust_schedule_last30d.py`.
- Runtime defaults remain safety-first: `AGENT_MODE=heuristic` and no-op execution adapter for dispatch.
- Weather runtime default is Open-Meteo; synthetic weather can be selected by config.
- Automatic weather-provider fallback chaining and run/manual-review API endpoints are still in progress.

## LLM Provider Configuration

The AI decision agent supports three providers, selected via the `LLM_PROVIDER` environment variable:

| `LLM_PROVIDER` | Default model | Requires |
|---|---|---|
| `openai` (default) | `gpt-4.1` | `OPENAI_API_KEY` |
| `anthropic` | `claude-3-7-sonnet` | `ANTHROPIC_API_KEY` |
| `ollama` | `llama3.2` | Running Ollama server (`OLLAMA_BASE_URL`) |

Override the model with `LLM_MODEL`. See [LangChain Config Spec](docs/LANGCHAIN_CONFIG_SPEC.md) for full details.

## Document Map

- [Architecture](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [Orchestration Backbone](docs/ORCHESTRATION.md)
- [AI Agent Specification](docs/AI_AGENT_SPEC.md)
- [Prompts and Rules (Normative Policy Source)](docs/PROMPTS_AND_RULES.md)
- [LangChain Configuration Spec](docs/LANGCHAIN_CONFIG_SPEC.md)
- [Traceability Spec](docs/TRACEABILITY.md)
- [Risk Register](docs/RISK_REGISTER.md)
- [Assumptions](docs/ASSUMPTIONS.md)
- [Design Review Checklist](docs/DESIGN_REVIEW_CHECKLIST.md)
- [Implementation Readiness Checklist](docs/IMPLEMENTATION_READINESS.md)
- [Baseline Schedule – Alabama Best Practices](docs/BASELINE_SCHEDULE_ALABAMA.md)

## Config Examples

- [LangChain config example](config/langchain.config.example.yaml)
- [Scheduler config example](config/scheduler.config.example.yaml)
- [Rules policy example](config/rules.policy.example.yaml)

## Seed Data

- [Alabama baseline schedule (SQL)](config/seeds/alabama_baseline_schedule.sql)

## Source of Truth Rule

Runtime thresholds and decision policy are loaded from:

- `config/SPRINKLER_LLM_RULES.md`

Design-time policy narrative is documented in:

- [Prompts and Rules](docs/PROMPTS_AND_RULES.md)

Other documents must not redefine conflicting values.

## Intended Runtime Flow (Design)

1. Scheduler triggers a daily adjustment run.
2. Orchestrator collects baseline schedule + weather snapshots.
3. Agent generates a bounded recommendation.
4. Deterministic rule engine applies hard constraints.
5. Confidence gate chooses auto-apply or manual review path.
6. Execution adapter applies schedule to device and returns receipt.
7. Traceability artifacts are persisted for audit and replay.

## Not in v1

- Multi-device scheduling
- Zone-level optimization
- Autonomous model retraining
- Complex soil digital twin modeling

## To Do

- Add more tests with other LLM providers/models.
- Expand testing depth for the currently selected LLM.
- Improve observability transparency and make run-level behavior easier to track.
- Investigate why recommendations currently reduce/skip in practice and rarely increase.
- Future-proof operational setup for production readiness.
- Implement scheduled trigger every 6 hours to refresh sprinkler schedules.
