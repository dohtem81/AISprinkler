# Database Schema Specification

## 1. Purpose

Define persistent entities needed for schedule adjustment, execution, and traceability.

Database target: PostgreSQL.

## 2. Core Entities

### 2.1 device

Represents the single target device in v1.

Fields:

- id uuid primary key
- name text not null
- device_type text not null
- timezone text not null
- location_lat numeric(9,6) not null
- location_lon numeric(9,6) not null
- status text not null default 'active'
- created_at timestamptz not null
- updated_at timestamptz not null

### 2.2 baseline_schedule

Stores daily preset schedule with optional seasonal context.

day_of_week convention: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday.
This matches Python datetime.weekday() to simplify orchestrator queries.

season_code values: summer, spring, fall, winter, all.
effective_month_start and effective_month_end use calendar month numbers 1-12.
When effective_month_end < effective_month_start (e.g., winter: 12-2), the orchestrator
treats this as a year-wrap range: month >= start OR month <= end.

Fields:

- id uuid primary key
- device_id uuid not null references device(id)
- day_of_week smallint not null check (day_of_week between 0 and 6)
- season_code text not null default 'all' check (season_code in ('summer','spring','fall','winter','all'))
- effective_month_start smallint not null default 1 check (effective_month_start between 1 and 12)
- effective_month_end smallint not null default 12 check (effective_month_end between 1 and 12)
- grass_type text
- start_time time not null
- duration_minutes integer not null check (duration_minutes > 0)
- is_active boolean not null default true
- notes text
- created_at timestamptz not null
- updated_at timestamptz not null

### 2.3 weather_observation

Observed weather history.

Fields:

- id uuid primary key
- device_id uuid not null references device(id)
- observed_at timestamptz not null
- rainfall_mm numeric(8,2) not null
- temperature_c numeric(6,2)
- humidity_pct numeric(5,2)
- provider text not null
- raw_payload jsonb not null
- created_at timestamptz not null

### 2.4 weather_forecast_snapshot

Forecast snapshot used in a run.

Fields:

- id uuid primary key
- device_id uuid not null references device(id)
- forecast_generated_at timestamptz not null
- horizon_hours integer not null check (horizon_hours = 24)
- rain_forecast_mm numeric(8,2) not null
- rain_probability_pct numeric(5,2)
- provider text not null
- provider_rank smallint not null
- raw_payload jsonb not null
- created_at timestamptz not null

### 2.5 adjustment_run

One orchestration run for daily adjustment.

Fields:

- id uuid primary key
- correlation_id uuid not null unique
- device_id uuid not null references device(id)
- run_date date not null
- state text not null
- trigger_type text not null
- confidence_threshold numeric(4,3) not null
- started_at timestamptz not null
- finished_at timestamptz
- created_at timestamptz not null

### 2.6 agent_recommendation

Raw and normalized recommendation from the agent.

Fields:

- id uuid primary key
- run_id uuid not null references adjustment_run(id)
- model_name text not null
- model_version text not null
- prompt_version text not null
- recommendation_action text not null
- recommended_duration_minutes integer
- confidence_score numeric(4,3) not null
- rationale text not null
- constraints_suggested jsonb not null
- output_payload jsonb not null
- created_at timestamptz not null

### 2.7 rule_evaluation

Deterministic rule outcomes applied after agent output.

Fields:

- id uuid primary key
- run_id uuid not null references adjustment_run(id)
- rule_id text not null
- rule_version text not null
- matched boolean not null
- effect text not null
- details jsonb not null
- created_at timestamptz not null

### 2.8 final_schedule_adjustment

Final approved action after rule and confidence gate.

Fields:

- id uuid primary key
- run_id uuid not null references adjustment_run(id)
- baseline_duration_minutes integer not null
- final_action text not null
- final_duration_minutes integer
- auto_applied boolean not null
- manual_review_required boolean not null
- approved_by text
- approval_reason text
- created_at timestamptz not null

### 2.9 execution_receipt

Execution contract result from adapter.

Fields:

- id uuid primary key
- run_id uuid not null references adjustment_run(id)
- dispatched_at timestamptz not null
- completed_at timestamptz
- status text not null
- executor_name text not null
- timeout_seconds integer not null
- retry_count integer not null
- command_payload jsonb not null
- response_payload jsonb
- error_message text
- created_at timestamptz not null

### 2.10 audit_event

Append-only audit stream.

Fields:

- id uuid primary key
- correlation_id uuid not null
- entity_type text not null
- entity_id uuid not null
- event_type text not null
- actor text not null
- event_payload jsonb not null
- occurred_at timestamptz not null

## 3. Indexing

Required indexes:

- baseline_schedule(device_id, season_code, is_active)
- baseline_schedule(device_id, day_of_week, season_code, is_active)
- weather_observation(device_id, observed_at desc)
- weather_forecast_snapshot(device_id, forecast_generated_at desc)
- adjustment_run(device_id, run_date desc)
- agent_recommendation(run_id)
- final_schedule_adjustment(run_id)
- execution_receipt(run_id, status)
- audit_event(correlation_id, occurred_at)

## 4. Retention Policy (Design)

- weather_observation: retain 24 months.
- weather_forecast_snapshot: retain 12 months.
- adjustment_run and linked decision artifacts: retain 36 months.
- audit_event: retain 36 months minimum, longer if operationally required.

## 5. Migration Strategy

- Use forward-only migrations with reversible scripts when possible.
- Seed one default device and baseline schedule for design validation scenarios.
- Version table schemas alongside docs and policy versions.
