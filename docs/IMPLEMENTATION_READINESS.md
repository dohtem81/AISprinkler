# Implementation Readiness Checklist

## Foundation

- [x] Define API contracts for orchestrator endpoints.
- [ ] Finalize doc set and lock versions.
- [ ] Choose migration tool and initialize migration baseline.

## Data Layer

- [x] Create initial PostgreSQL schema from DATABASE_SCHEMA.md.
- [x] Seed sample baseline schedule and weather records.
- [ ] Validate index performance on expected query paths.

## Orchestration Layer

- [x] Implement run state machine exactly as documented.
- [ ] Implement dedupe and idempotency keys in trigger + dispatch runtime paths.
- [ ] Implement retry matrix and dead-letter handling.

## AI Layer

- [x] Implement prompt stack and strict output parser.
- [ ] Implement policy lookup by version.
- [x] Implement confidence gate routing.

## Integration Layer

- [ ] Implement weather provider primary and fallback adapters.
- [ ] Implement execution adapter command/response contract.
- [ ] Implement structured logging with correlation id propagation.

## Product Surface

- [ ] Implement dashboard APIs for run monitoring and manual review workflow.
- [ ] Implement manual override endpoint with full audit trail.
- [x] Provide scripted historical replay for run reconstruction (`scripts/adjust_schedule_last30d.py`).
- [ ] Implement production replay API/job orchestration for run reconstruction.

## Traceability and Ops

- [ ] Persist all mandatory run artifacts.
- [ ] Expose minimum metrics and alert thresholds.
- [ ] Validate replayability on one end-to-end run.
- [ ] Add hard safety guardrails for overwatering prevention at dispatch boundary.

## Exit Criteria

- [ ] Daily run can complete in auto-apply path.
- [ ] Daily run can complete in manual-review path.
- [ ] Failure path falls back safely to baseline.
- [ ] Audit trail allows full run reconstruction.

## Current Reality Check (April 2026)

- Implemented now: core run state orchestration, Open-Meteo weather ingestion with persistence, configurable agent mode (`heuristic` and `langchain`), schedule persistence/query APIs, and agent trace persistence.
- Missing for production: runtime fallback weather chain, non-noop hardware actuation, completed run/manual review APIs, robust retry/dead-letter behavior, production replay service/API workflows, and full observability/alert coverage.

## To Do (Priority Backlog)

- [ ] Add more tests with other LLM providers/models.
- [ ] Expand testing depth for the current LLM profile.
- [ ] Increase observability transparency and make run behavior easier to track.
- [ ] Investigate why recommendations currently trend toward reduction and rarely increase duration.
- [ ] Future-proof deployment posture for production-grade operations.
- [ ] Implement scheduled trigger every 6 hours to refresh sprinkler schedules.
