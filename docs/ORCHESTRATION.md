# Orchestration Backbone Specification

## 1. Purpose

Define trigger cadence, state transitions, retries, and execution contract for schedule adjustment runs.

## 2. Trigger Model

### 2.1 Scheduled Trigger

Primary run at local 06:00 daily.

Operational note:

- A recurring 6-hour trigger cadence is planned but not yet implemented.

Trigger id format:

- daily:<device_id>:<yyyy-mm-dd>

### 2.2 Event Trigger (Optional)

Weather-impact trigger can request re-evaluation when forecast freshness or rain event threshold indicates significant change.

Trigger id format:

- event:<device_id>:<event_type>:<timestamp>

Current implementation status:

- Daily trigger path is implemented via Celery task.
- Manual forecast refresh is implemented via `POST /api/v1/weather/refresh`.
- Event-triggered reevaluation is planned but not implemented in runtime workflow.

### 2.3 Real-Time vs Batch Event Flow

Real-time control loop (minutes):

1. Receive weather/device signal.
2. Recompute context for impacted device.
3. Run decision + deterministic rule check.
4. Route to auto-apply or manual review.

Batch loop (hourly/daily):

1. Reconcile missing artifacts and stale runs.
2. Produce operational summaries and drift reports.
3. Execute historical replay jobs for policy/model validation.

Repository alignment:

- Current code supports daily trigger and per-run orchestration use case.
- Scripted historical replay exists (`scripts/adjust_schedule_last30d.py`); productized replay service/API and event-driven loop remain roadmap items.

## 3. Run State Machine

States:

- queued
- collecting_data
- reasoning
- rule_check
- approval_gate
- dispatching
- verifying
- closed
- failed
- manual_review

State rules:

1. Exactly one terminal state: closed, failed, or manual_review.
2. State writes must be idempotent and ordered by run sequence.
3. Retry may re-enter collecting_data or dispatching but must keep same run id.

## 4. Workflow Steps

1. Create run and correlation id.
2. Load active baseline schedule for run date.
3. Pull weather observations for last 24h and forecast for next 24h.
	- Weather persistence stores hourly forecast horizon for next 7 days; decision features are derived from that data.
4. Invoke agent with normalized payload.
5. Apply deterministic rules.
6. Evaluate confidence gate.
7. If auto path, dispatch command to adapter.
8. Persist execution receipt and close run.
9. If below threshold, move to manual_review queue.

## 5. Confidence Gate

Normative thresholds are defined in policy source:

- docs/PROMPTS_AND_RULES.md

Behavior:

- confidence >= threshold: auto apply
- confidence < threshold: require manual review

## 6. Retry Matrix

- Weather provider timeout: retry up to 2 times per provider then fallback provider.
- Agent timeout: retry once with same model, then fallback model profile.
- Adapter timeout: retry once with same payload and idempotency key.
- Persistent DB failure: mark run failed and emit high-severity alert.

Current implementation status:

- Celery task retry wrapper exists.
- Per-step retry/fallback policies inside orchestrated steps are only partially implemented.
- Current task configuration retries whole-task failures (max 2 retries); provider-specific fallback chaining is not yet wired.

## 7. Idempotency and Dedupe

Keys:

- run dedupe key: <device_id>:<run_date>:<trigger_type>
- dispatch idempotency key: <run_id>:<final_action>

Rules:

- Duplicate trigger with same dedupe key returns existing active run.
- Duplicate dispatch with same idempotency key does not send second command.

## 8. Script and Adapter Contract

Command payload schema:

- run_id string
- device_id string
- action one of keep|reduce|skip|increase
- final_duration_minutes integer or null for skip
- effective_start_time string
- correlation_id string

Response payload schema:

- accepted boolean
- adapter_execution_id string
- started_at timestamp
- completed_at timestamp or null
- status one of success|partial|failed|timeout
- proof object (echoed action, duration, adapter checksum)
- error object nullable

## 9. Failure Fallback Behavior

Target behavior:

- If data collection cannot produce safe weather context, fallback to baseline action.
- If agent cannot return valid schema after retries, fallback to baseline action and mark low confidence.
- If adapter fails after retry, run remains failed and must be manually reconciled.

Safety baseline in current runtime path:

- Weather provider is selected via `WEATHER_PROVIDER`; `open_meteo` remains the
  default and `synthetic` is still available by config.
- Manual forecast refresh uses the configured provider through a provider-neutral
  refresh contract and returns a configuration error when the provider does not
  support forecast refresh.
- Agent defaults to heuristic mode unless `AGENT_MODE=langchain` is configured.
- Execution uses no-op adapter, preventing accidental real hardware writes while adapter hardening is incomplete.
- On weather-provider/agent errors, current flow relies on task retry and may
  still end in failed state; baseline fallback routing is not fully implemented yet.

## 10. Trigger Script Blueprint (Design)

Planned entry points:

- scripts/trigger_daily_adjustment.py
- scripts/retry_failed_run.py
- scripts/process_manual_reviews.py
- scripts/create_baseline_last30d.py
- scripts/adjust_schedule_last30d.py

Current Docker runtime note:

- The `app` image does not include repository `scripts/` by default.
- Run script entry points with a bind mount.

Script command examples:

- Trigger daily adjustment:
	- `docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/trigger_daily_adjustment.py`
- Retry failed run:
	- `docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/retry_failed_run.py <run_id>`
- Process manual reviews:
	- `docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/process_manual_reviews.py`
- Pull weather history:
	- `docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/weather_spanishfort.py`
- Create baseline history:
	- `docker compose -f docker/docker-compose.yml run --rm -v "$PWD/scripts:/app/scripts:ro" app python /app/scripts/create_baseline_last30d.py`
- Replay adjustments with LangChain:
	- `docker compose -f docker/docker-compose.yml --profile local-llm run --rm -v "$PWD/scripts:/app/scripts:ro" -e AGENT_MODE=langchain app python /app/scripts/adjust_schedule_last30d.py`

Each script must:

1. Accept run context arguments.
2. Emit structured logs with correlation id.
3. Exit with stable non-zero code on hard failure.
