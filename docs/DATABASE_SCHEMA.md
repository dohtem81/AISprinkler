# Database Schema Specification

## 1. Purpose

Define the persisted entities needed for schedule visibility, run orchestration, and traceability.

Database target: PostgreSQL.

## 2. Implemented Tables

### 2.1 device

Represents the single target device in v1.

Fields:

- id uuid primary key
- name text not null
- device_type text not null
- timezone text not null
- location_lat numeric/float not null
- location_lon numeric/float not null
- status text not null default `active`
- created_at timestamptz not null
- updated_at timestamptz not null

### 2.2 original_baseline_schedule

Append-only original baseline rows for concrete calendar dates.

Intent:

- Preserve the seeded or imported baseline plan.
- Store one or more watering slots for specific dates.
- Keep the original baseline separate from operator- or AI-adjusted current rows.

Fields:

- id uuid primary key
- device_id uuid not null references device(id)
- schedule_date date not null
- grass_type text null
- start_time time not null
- duration_minutes integer not null
- is_active boolean not null default true
- notes text null
- source text not null
- created_at timestamptz not null
- updated_at timestamptz not null

### 2.3 current_baseline_schedule

Visible schedule rows for concrete calendar dates.

Intent:

- Drive the schedule the system currently considers active.
- Keep history by superseding rows instead of deleting them.
- Support week-ahead visibility without losing prior values.

Fields:

- id uuid primary key
- device_id uuid not null references device(id)
- original_schedule_id uuid null references original_baseline_schedule(id)
- schedule_date date not null
- grass_type text null
- start_time time not null
- duration_minutes integer not null
- is_active boolean not null default true
- notes text null
- source text not null
- superseded_at timestamptz null
- created_at timestamptz not null
- updated_at timestamptz not null

History rule:

- Current rows are never hard-deleted as part of normal operation.
- Replacements create a new visible row and mark the previous visible row with `superseded_at`.

### 2.4 adjustment_run

One orchestration run for daily adjustment.

Fields:

- id uuid primary key
- correlation_id uuid not null unique
- device_id uuid not null references device(id)
- run_date date not null
- state text not null
- trigger_type text not null
- confidence_threshold numeric/float not null
- started_at timestamptz not null
- finished_at timestamptz null
- created_at timestamptz not null

### 2.5 agent_prompt_exchange

Append-only prompt and response history for agent decisions.

Intent:

- Persist the exact prompt/response exchange used for a run.
- Retain prompt and policy versions for replay and audit.
- Keep structured request/response payloads alongside raw text.

Fields:

- id uuid primary key
- run_id uuid not null references adjustment_run(id)
- correlation_id uuid not null
- model_name text not null
- model_version text not null
- prompt_version text not null
- policy_version text not null
- prompt_text text not null
- response_text text not null
- request_payload json/jsonb not null
- response_payload json/jsonb not null
- created_at timestamptz not null

### 2.6 audit_event

Append-only audit stream.

Fields:

- id uuid primary key
- correlation_id uuid not null
- entity_type text not null
- entity_id uuid not null
- event_type text not null
- actor text not null
- event_payload json/jsonb not null
- occurred_at timestamptz not null

### 2.7 weather_location

Registry of locations queried for weather forecasts, keyed by zipcode.

Intent:

- Normalise location metadata (city, state, lat/lon) away from the per-hour forecast rows.
- Allow multiple forecast rows to reference one canonical location record.
- Zipcode is the external key used when calling weather APIs.

Fields:

- id uuid primary key
- zipcode text(10) not null unique (e.g. `35201`; US 5-digit format; stored as string to preserve leading zeros)
- city text null
- state_code text(2) null (e.g. `AL`)
- country_code text(2) not null default `US`
- location_lat float null
- location_lon float null
- created_at timestamptz not null
- updated_at timestamptz not null

### 2.8 weather_forecast_hour

Hourly weather data — one row per (location, forecast hour, provider).

Intent:

- Store per-hour weather data as fetched from weather providers.
- Retain both live forecasts and verified historical observations; `is_observed` flips from false to true once the hour is in the past and the row is refreshed from an observations endpoint.
- Enable day-level aggregation (e.g. daily rain total) via the denormalised `forecast_date` column.
- Support overwrite semantics for upcoming forecast windows: before insert/update,
  the write path clears future non-observed rows for the same `(location_id, provider)`
  and then upserts the fresh horizon.
- Keep unique upsert key `(location_id, forecast_hour, provider)` to prevent duplicates.
- Multiple providers can coexist for the same location/hour for comparison or fallback.

Fields:

- id uuid primary key
- location_id uuid not null references weather_location(id)
- forecast_date date not null (denormalised from forecast_hour for efficient date-range queries)
- forecast_hour timestamptz not null (UTC start of the hour this row represents)
- temperature_c float null
- feels_like_c float null
- humidity_pct float null
- rain_mm float null (precipitation total for this hour)
- snow_mm float null
- rain_probability_pct float null (0–100)
- wind_speed_kmh float null
- wind_direction_deg integer null
- weather_code text null (provider-specific condition code, e.g. OWM icon code or WMO code)
- weather_description text null
- is_observed boolean not null default false (false = still a forecast; true = verified historical observation)
- provider text not null
- fetched_at timestamptz not null (wall-clock time this row was written from the API)
- created_at timestamptz not null

Unique constraint:

- `(location_id, forecast_hour, provider)` — prevents duplicate rows per provider per hour; use `ON CONFLICT` for upsert.

## 3. Startup Schema Management

Startup behavior for managed tables:

- Create missing tables from the application metadata.
- Add missing columns for managed tables.
- Seed a default device if it does not exist.
- Ensure both original and current baseline schedules are populated for the next 7 days.
- If a legacy weekday-based `baseline_schedule` table exists, expand it into dated rows for the visible week-ahead window.

Constraints:

- Startup schema sync is additive and non-destructive.
- Historical rows are preserved; the system does not drop prior current schedule versions during normal bootstrap.
- Destructive schema refactors still require an explicit migration plan.

## 4. Indexing

Implemented indexes:

- original_baseline_schedule(device_id, schedule_date)
- current_baseline_schedule(device_id, schedule_date, is_active, superseded_at)
- adjustment_run(correlation_id unique)
- agent_prompt_exchange(correlation_id)
- audit_event(correlation_id, occurred_at)
- weather_location(zipcode unique)
- weather_forecast_hour(location_id, forecast_date)
- weather_forecast_hour(location_id, forecast_hour)
- weather_forecast_hour(location_id, forecast_hour, provider) — unique

## 5. Retention Policy

- original_baseline_schedule: retain indefinitely unless explicitly archived.
- current_baseline_schedule: retain indefinitely for history and audit.
- adjustment_run: retain at least 36 months.
- agent_prompt_exchange: retain at least 36 months.
- audit_event: retain at least 36 months minimum, longer if operationally required.
- weather_location: retain indefinitely (small reference table).
- weather_forecast_hour: retain at least 36 months for seasonal pattern analysis; older rows may be archived after verified observations are confirmed.

## 6. Production Requirements

- Credentials, API keys, device identifiers, and similar sensitive values must not be stored in the repository.
- Production deployments must source those values from Docker secrets or an external secret manager.
- Local bootstrap defaults are for development only and must not be treated as production-safe configuration.
