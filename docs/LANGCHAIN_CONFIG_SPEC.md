# LangChain Configuration Specification

## 1. Purpose

Specify runtime configuration profile for the AI decision layer.

## 2. Model Policy

Primary model profile:

- provider: openai
- model: gpt-4.1
- temperature: 0.2
- max_output_tokens: 800

Fallback model profile:

- provider: anthropic
- model: claude-3-7-sonnet
- temperature: 0.2
- max_output_tokens: 800

## 3. Tool Registry

Required tool interfaces:

- get_baseline_schedule
- get_rain_last_24h
- get_forecast_next_24h
- get_policy_snapshot

Tool timeout defaults:

- weather tools: 4000 ms
- database lookup tools: 2000 ms

## 4. Runtime Controls

- max_agent_iterations: 5
- agent_timeout_ms: 15000
- schema_validation_required: true
- retries_on_schema_error: 1
- retries_on_model_timeout: 1

## 5. Memory Strategy

- memory_mode: run_scoped
- persist_cross_run_memory: false

Rationale:

- Reproducibility improves when each run is isolated and fully captured in explicit inputs.

## 6. Callback and Tracing

Callbacks must capture:

- correlation_id
- run_id
- model metadata
- prompt_version
- policy_version
- token usage
- latency by step

## 7. Output Parsing Contract

Use strict parser bound to documented JSON schema.

On parse failure:

1. Issue one schema-reminder retry.
2. If second failure occurs, mark recommendation unavailable and route to safe fallback path.

## 8. Provider Fallback Behavior

- If primary weather provider fails freshness or availability checks, use secondary provider.
- If model provider fails, route to fallback model profile.
- When fallback path is used, add confidence penalty as defined in policy process notes.

## 9. Configuration Management

- Keep config in versioned yaml files.
- Include config version in run artifacts.
- Any runtime-affecting change requires changelog entry and review.
