# Traceability Specification

## 1. Purpose

Define minimum artifacts and correlation strategy required for end-to-end auditability.

## 2. Correlation Standard

Every run must carry one correlation id (uuid) from trigger to final receipt.

Mandatory propagation points:

- scheduler trigger event
- orchestration logs
- weather provider requests
- agent invocation and callbacks
- DB writes for decision artifacts
- execution adapter command and response

## 3. Mandatory Run Artifacts

For each run, persist:

1. Input Snapshot
- baseline schedule
- weather history and forecast
- policy and prompt versions

2. Decision Trace
- raw model output
- normalized parsed output
- confidence score and rationale
- persisted prompt/response exchange (exact sent prompt + received response)

3. Rule Evaluation Log
- rule id, matched state, and effect

4. Final Decision Record
- auto-apply or manual-review outcome
- final action and duration

5. Execution Receipt
- command payload
- adapter response
- outcome status

## 4. Audit Event Requirements

Each significant transition writes append-only event:

- run.created
- data.collected
- agent.recommended
- rules.applied
- gate.routed
- dispatch.sent
- dispatch.completed
- run.closed or run.failed

Audit event payload must include correlation id and entity references.

## 5. Observability Metrics

Minimum metrics:

- daily_run_count
- auto_apply_rate
- manual_review_rate
- fallback_weather_provider_rate
- fallback_model_rate
- average_decision_latency_ms
- execution_failure_rate

## 6. Replay and Reproducibility

### 5.1 Alert Thresholds

| Metric | Condition | Severity |
|---|---|---|
| execution_failure_rate | > 20 % over rolling 24 h | HIGH |
| auto_apply_rate | < 50 % over rolling 7 days | MEDIUM |
| manual_review_rate | > 40 % over rolling 7 days | MEDIUM |
| fallback_weather_provider_rate | > 30 % over rolling 24 h | MEDIUM |
| fallback_model_rate | > 10 % over rolling 24 h | HIGH |
| average_decision_latency_ms | p95 > 30 000 ms | MEDIUM |

A run is replayable when these conditions are met:

- input snapshot retained
- prompt and policy versions retained
- model metadata retained
- final rule effects retained

## 7. Query Patterns

Required operational queries:

- list runs by date and status
- fetch full artifact chain by correlation id
- compare recommendation vs final action deltas
- identify runs using fallback providers
- inspect sent prompt text and received model response by correlation id and timestamp
