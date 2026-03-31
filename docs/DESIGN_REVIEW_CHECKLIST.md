# Design Review Checklist

## Coverage

- [ ] Database schema covers schedules, weather, decisions, execution, and audit.
- [ ] Orchestration state machine and retry behavior are documented.
- [ ] AI output schema is strict and parseable.
- [ ] Confidence gate behavior is explicit.
- [ ] Trigger and adapter command contract is documented.
- [ ] Traceability artifacts are mandatory and complete.

## Consistency

- [ ] Threshold values match normative policy source.
- [ ] Action vocabulary is consistent across all docs.
- [ ] Run states are identical across architecture and orchestration docs.
- [ ] Policy and prompt versioning strategy is consistent.

## Resilience

- [ ] Weather fallback path is documented.
- [ ] Model fallback path is documented.
- [ ] Safe baseline fallback is documented.
- [ ] Manual review escalation path is documented.

## Operability

- [ ] Minimum metrics set is defined.
- [ ] Audit query requirements are defined.
- [ ] Correlation id propagation points are defined.

## Sign-off

- [ ] Product sign-off
- [ ] Backend sign-off
- [ ] AI/ML sign-off
- [ ] Operations sign-off
