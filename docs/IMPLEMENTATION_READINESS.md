# Implementation Readiness Checklist

## Foundation

- [ ] Finalize doc set and lock versions.
- [ ] Choose migration tool and initialize migration baseline.
- [ ] Define API contracts for orchestrator endpoints.

## Data Layer

- [ ] Create initial PostgreSQL schema from DATABASE_SCHEMA.md.
- [ ] Seed sample baseline schedule and weather records.
- [ ] Validate index performance on expected query paths.

## Orchestration Layer

- [ ] Implement run state machine exactly as documented.
- [ ] Implement dedupe and idempotency keys.
- [ ] Implement retry matrix and dead-letter handling.

## AI Layer

- [ ] Implement prompt stack and strict output parser.
- [ ] Implement policy lookup by version.
- [ ] Implement confidence gate routing.

## Integration Layer

- [ ] Implement weather provider primary and fallback adapters.
- [ ] Implement execution adapter command/response contract.
- [ ] Implement structured logging with correlation id propagation.

## Traceability and Ops

- [ ] Persist all mandatory run artifacts.
- [ ] Expose minimum metrics and alert thresholds.
- [ ] Validate replayability on one end-to-end run.

## Exit Criteria

- [ ] Daily run can complete in auto-apply path.
- [ ] Daily run can complete in manual-review path.
- [ ] Failure path falls back safely to baseline.
- [ ] Audit trail allows full run reconstruction.
