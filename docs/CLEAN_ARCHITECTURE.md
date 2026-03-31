# Clean Architecture Guide

## 1. Purpose

Capture the layering rules, dependency direction, and test strategy for the
AISprinkler Python codebase so that contributors can place new code in the
right layer without breaking the dependency inversion principle.

---

## 2. Layer Map

```
┌─────────────────────────────────────────────────────┐
│                     Entry Points                    │
│  api/  (FastAPI)   scripts/  (CLI)  tasks/  (Celery)│
├─────────────────────────────────────────────────────┤
│                  Infrastructure                     │
│  persistence/  weather/  agent/  executor/          │
│  scheduler/                                         │
├─────────────────────────────────────────────────────┤
│                   Application                       │
│  use_cases/   ports/   dtos/                        │
├─────────────────────────────────────────────────────┤
│                     Domain                          │
│  entities/  value_objects/  repositories/  services/│
└─────────────────────────────────────────────────────┘
```

Arrows of allowed imports go **inward only**:

```
Entry Points  →  Application  →  Domain
Infrastructure  →  Application  →  Domain
```

No layer may import from any layer further **out** than itself.

---

## 3. Layer Responsibilities

### 3.1 Domain  (`src/aisprinkler/domain/`)

The innermost ring.  Contains the business rules and nothing else.

| Sub-package | Contents | Rules |
|---|---|---|
| `entities/` | `Device`, `BaselineSchedule`, `AdjustmentRun` | Plain dataclasses; no I/O |
| `value_objects/` | `SeasonCode`, `WeatherContext`, `Recommendation` | Frozen dataclasses; immutable |
| `repositories/` | `ScheduleRepository`, `RunRepository` ABCs | Abstract only; no SQL |
| `services/` | `RuleEngine` | Pure functions; deterministic; no I/O |

**Allowed imports**: standard library only.  
**Forbidden imports**: SQLAlchemy, LangChain, FastAPI, Redis, httpx.

### 3.2 Application  (`src/aisprinkler/application/`)

Orchestration layer.  Describes *what* the system does in terms of domain objects.

| Sub-package | Contents | Rules |
|---|---|---|
| `use_cases/` | `RunDailyAdjustmentUseCase`, `ProcessManualReviewUseCase` | Constructor-inject all deps; no infrastructure imports |
| `ports/` | `WeatherPort`, `AgentPort`, `ExecutorPort` ABCs | Interfaces only; define the contract each adapter must fulfil |
| `dtos/` | `DailyAdjustmentRequest`, `DailyAdjustmentResult` | Frozen dataclasses; plain Python types |

**Allowed imports**: domain layer, standard library.  
**Forbidden imports**: SQLAlchemy, LangChain, FastAPI, Redis, httpx.

### 3.3 Infrastructure  (`src/aisprinkler/infrastructure/`)

Adapters that make external systems conform to the application's ports.

| Sub-package | Implements | Key classes |
|---|---|---|
| `persistence/` | `ScheduleRepository`, `RunRepository` | `SqlAlchemyScheduleRepository`, `SqlAlchemyRunRepository` |
| `weather/` | `WeatherPort` | `OpenWeatherAdapter`, `WeatherApiFallbackAdapter` |
| `agent/` | `AgentPort` | `LangChainAgentAdapter` |
| `executor/` | `ExecutorPort` | `GenericDeviceAdapter`, `NoOpDeviceAdapter` |
| `scheduler/` | Celery entry points | `celery_app`, `tasks` |

**Allowed imports**: application layer, domain layer, any third-party library.

### 3.4 Entry Points  (`api/`, `scripts/`)

Thin adapters that accept external input, build a use-case request DTO, call the
use case, and return the result.

| Package | Role |
|---|---|
| `api/` | FastAPI routes → call use cases |
| `scripts/` | CLI entry points → call use cases |
| `infrastructure/scheduler/tasks.py` | Celery tasks → call use cases |

**Allowed imports**: application layer, infrastructure (for dependency wiring), standard library.

---

## 4. Dependency Injection

Use cases receive all collaborators through their `__init__` constructor.
No use case instantiates a concrete class directly.

```python
# Correct: infrastructure wires concrete adapters into the use case
# LLM_PROVIDER env var selects openai | anthropic | ollama at runtime
agent = LangChainAgentAdapter(
    provider=os.getenv("LLM_PROVIDER", "openai"),   # or "ollama" for local
    model_name=os.getenv("LLM_MODEL"),               # None → provider default
    ollama_base_url=os.getenv("OLLAMA_BASE_URL"),    # ignored unless provider=ollama
)

use_case = RunDailyAdjustmentUseCase(
    schedule_repo=SqlAlchemyScheduleRepository(session),
    run_repo=SqlAlchemyRunRepository(session),
    weather_port=OpenWeatherAdapter(api_key=settings.openweather_key),
    agent_port=agent,
    executor_port=GenericDeviceAdapter(device_config=device_cfg),
    rule_engine=RuleEngine(),
    confidence_threshold=settings.confidence_auto_apply_threshold,
)
```

This pattern makes it trivial to swap any adapter — including the LLM provider — in
tests or production with no code changes.

---

## 5. Test Strategy

```
┌──────────────────────────────────────────────────────────┐
│ tests/e2e/               Full HTTP round-trip (minimal)  │
├──────────────────────────────────────────────────────────┤
│ tests/integration/       Real DB (docker-compose service)│
│   test_schedule_repository.py                            │
│   test_run_repository.py  (TODO)                         │
├──────────────────────────────────────────────────────────┤
│ tests/unit/application/  Use cases — all ports mocked    │
│   test_run_daily_adjustment.py                           │
├──────────────────────────────────────────────────────────┤
│ tests/unit/domain/       Pure logic — no mocks needed    │
│   test_rule_engine.py                                    │
│   test_entities.py                                       │
└──────────────────────────────────────────────────────────┘
```

### Rules

- **Unit tests** (domain + application): zero infrastructure imports.  
  Mock every port using `AsyncMock(spec=PortClass)`.
- **Integration tests**: real PostgreSQL via docker-compose service, rolled back after each test.
  Import from `infrastructure.persistence` only.
- **E2E tests**: spin up the full docker-compose stack; test HTTP endpoints.
- **Execution policy**: run all tests from Docker Compose (no host-level `pytest`).

### Running tests

```bash
# Unit tests in Docker
make test-unit

# Integration tests in Docker
make test-integration

# All tests with coverage in Docker
make test-cov
```

---

## 6. Adding a New Feature – Checklist

1. **Domain first**: define or extend entities / value objects / services.
2. **Port second**: if a new external system is needed, add an ABC to `application/ports/`.
3. **Use case third**: write or extend the use case; inject the new port.
4. **Infrastructure fourth**: write the concrete adapter implementing the port.
5. **Wire last**: add the adapter to the entry-point wiring (API router / Celery task).
6. **Test at every layer**: unit test the use case with a mock port; integration test the adapter.

---

## 7. Anti-Patterns to Avoid

| Anti-pattern | Why it's harmful |
|---|---|
| SQLAlchemy model imported inside a use case | Breaks the inward-only dependency rule; makes unit tests require a DB |
| Hardcoded threshold values inside entities | Normative values must live in `PROMPTS_AND_RULES.md` and flow in via config |
| LangChain objects created inside a use case | LLM is an infrastructure detail; use `AgentPort` |
| Use case calling `os.environ` directly | Config should be injected; makes tests brittle |
| Repository ABC importing infrastructure models | Repo interfaces belong to domain; models belong to infrastructure |
