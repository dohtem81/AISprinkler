# AI Agent Specification

## 1. Purpose

Define how the AI component proposes schedule adjustments while remaining bounded by deterministic policy.

## 2. Agent Role

The agent recommends one action for the next 24 hours:

- keep
- reduce
- skip
- increase

The agent does not execute commands and does not override hard rules.

## 3. Inputs

- baseline schedule for target day
- rainfall observed in last 24h
- rain forecast for next 24h
- optional context (temperature, humidity, wind)
- policy metadata and current threshold version

## 4. Output Contract

Output must be valid JSON with fields:

- recommendation_action: keep|reduce|skip|increase
- recommended_duration_minutes: integer|null
- confidence_score: number between 0 and 1
- rationale: non-empty string
- assumptions: array of strings
- policy_version: string
- weather_source_summary: object

Invalid output is rejected and retried under orchestration policy.

## 5. Decision Policy Link

Normative threshold and bound definitions are in:

- docs/PROMPTS_AND_RULES.md

Agent must not exceed policy bounds.

## 6. Prompt Stack

- System policy prompt: role, constraints, safety behavior
- Decision rubric prompt: scoring and action guidance
- Tool usage prompt: how and when tools can be called
- Output schema prompt: exact JSON contract

## 7. Tool Contract (Design)

Minimum tools:

- get_baseline_schedule(device_id, run_date)
- get_rain_last_24h(device_id, as_of)
- get_forecast_next_24h(device_id, as_of)
- get_policy_snapshot(policy_version)

Optional tools:

- get_historical_run_summary(device_id, days)

## 8. Failure Handling

- Schema validation failure: retry with schema reminder prompt.
- Low confidence output: send to manual review path.
- Missing weather data: apply fallback provider logic before agent call.

## 9. Safety Constraints

- Deterministic rules always applied after agent output.
- Agent cannot bypass manual review when confidence is below threshold.
- Agent cannot set negative duration or unsupported actions.

## 10. Versioning

Each recommendation must store:

- model_name
- model_version
- prompt_version
- policy_version

This enables replay and audit reproduction.
