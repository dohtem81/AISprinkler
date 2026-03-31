# Risk Register

## R1 Weather Data Unavailable

- Impact: wrong or delayed decisions
- Likelihood: medium
- Mitigation: dual provider fallback, freshness checks, baseline fallback path

## R2 LLM Schema Instability

- Impact: orchestration interruption or unsafe parse
- Likelihood: medium
- Mitigation: strict parser, schema retry, fallback routing

## R3 Over-Adjustment Risk

- Impact: under-watering or over-watering
- Likelihood: medium
- Mitigation: deterministic clamp, confidence gate, hard skip rules

## R4 Adapter Execution Failure

- Impact: schedule not applied
- Likelihood: low to medium
- Mitigation: idempotent dispatch, one retry, manual reconciliation queue

## R5 Silent Trace Gaps

- Impact: lost auditability
- Likelihood: low
- Mitigation: mandatory artifact checklist, correlation-id validation in pipeline

## R6 Policy Drift Across Docs

- Impact: inconsistent system behavior during implementation
- Likelihood: medium
- Mitigation: single normative policy source and review gate
