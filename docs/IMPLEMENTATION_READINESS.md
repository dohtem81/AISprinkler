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
- [x] Implement dedupe and idempotency keys.
- [ ] Implement retry matrix and dead-letter handling.

## AI Layer

- [x] Implement prompt stack and strict output parser.
- [x] Implement policy lookup by version.
- [x] Implement confidence gate routing.

## Integration Layer

- [x] Implement weather provider primary and fallback adapters.
- [x] Implement execution adapter command/response contract.
- [x] Implement structured logging with correlation id propagation.

## Traceability and Ops

- [x] Persist all mandatory run artifacts.
- [x] Expose minimum metrics and alert thresholds.
- [x] Validate replayability on one end-to-end run.

## Exit Criteria

- [x] Daily run can complete in auto-apply path.
- [x] Daily run can complete in manual-review path.
- [x] Failure path falls back safely to baseline.
- [x] Audit trail allows full run reconstruction.

## To Do (Priority Backlog)

- [ ] Add more tests with other LLM providers/models.
- [ ] Expand testing depth for the current LLM profile.
- [ ] Increase observability transparency and make run behavior easier to track.
- [ ] Investigate why recommendations currently trend toward reduction and rarely increase duration.
- [ ] Future-proof deployment posture for production-grade operations.
- [ ] Implement scheduled trigger every 6 hours to refresh sprinkler schedules.
