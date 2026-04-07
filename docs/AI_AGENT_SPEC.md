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

Current implementation note:

- Invalid JSON currently raises an error in adapter parsing.
- There is no dedicated schema-reminder retry loop in the adapter yet; retries occur at the task/orchestration level.

## 5. Decision Policy Link

Normative threshold and bound definitions are in:

- docs/PROMPTS_AND_RULES.md

Agent must not exceed policy bounds.

## 6. Prompt Stack

- System policy prompt: role, constraints, safety behavior
- Decision rubric prompt: scoring and action guidance
- Tool usage prompt: how and when tools can be called
- Output schema prompt: exact JSON contract

Runtime note:

- Prompt/rule text is loaded from `config/SPRINKLER_LLM_RULES.md`.
- Runtime includes a post-parse guard to coerce obviously invalid or copied-example style outputs into safe, policy-consistent recommendations.

## 7. Tool Contract (Design)

Minimum tools:

- get_baseline_schedule(device_id, run_date)
- get_rain_last_24h(device_id, as_of)
- get_forecast_next_24h(device_id, as_of)
- get_policy_snapshot(policy_version)

Optional tools:

- get_historical_run_summary(device_id, days)

## 8. Failure Handling

- Schema validation failure: target behavior is retry with schema reminder prompt.
- Low confidence output: send to manual review path.
- Missing weather data: target behavior is fallback provider logic before agent call.

Current implementation note:

- Low-confidence routing is implemented.
- Schema-reminder retry and provider fallback chaining are not fully implemented in runtime path yet.

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

## 11. LLM Provider Configuration

The agent implementation supports multiple LLM providers, selected at runtime without
code changes.

Selection order (highest priority first):

1. `provider` constructor argument
2. `LLM_PROVIDER` environment variable
3. Default: `openai`

Supported providers:

| Provider | `LLM_PROVIDER` value | Default model | API key required |
|---|---|---|---|
| OpenAI | `openai` | `gpt-4.1` | Yes — `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `claude-3-7-sonnet` | Yes — `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama` | `llama3.2` | No — set `OLLAMA_BASE_URL` |

Model name is independently overridable via the `LLM_MODEL` env var or constructor
argument.  This keeps the model name orthogonal to the provider choice.

Ollama-specific notes:

- Any model pulled via `ollama pull <model>` can be used.
- Smaller models may require raising `retries_on_schema_error` due to less reliable
  JSON output.
- `model_version` in the stored `Recommendation` will be empty for Ollama (not
  returned by the Ollama API).

Full configuration reference: `docs/LANGCHAIN_CONFIG_SPEC.md §9`.
