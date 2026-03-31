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

## 9. Ollama Provider (Local / Air-Gapped)

Ollama allows running open-source LLMs locally without an API key.  It is selected
by setting `LLM_PROVIDER=ollama` in the environment.

| Parameter | Env var | Default |
|---|---|---|
| Provider | `LLM_PROVIDER` | `openai` |
| Model | `LLM_MODEL` | `llama3.2` |
| Server URL | `OLLAMA_BASE_URL` | `http://localhost:11434` |

### Quickstart

```bash
# 1. Pull the model on the host running Ollama
ollama pull llama3.2

# 2. Set env vars in .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434   # or http://ollama:11434 if added to compose

# 3. Run normally
make dev
```

### Adding Ollama as a Docker Compose service (optional)

Add the following service to `docker/docker-compose.yml` to run Ollama inside the
compose stack:

```yaml
ollama:
  image: ollama/ollama:latest
  volumes:
    - ollama_data:/root/.ollama
  expose:
    - "11434"
```

Then set `OLLAMA_BASE_URL=http://ollama:11434` in the `app` / `worker` service
environment.

### Limitations

- Ollama does not require an API key; `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are
  ignored when `LLM_PROVIDER=ollama`.
- Output quality depends on the chosen model.  Smaller models may not reliably
  produce the required JSON schema — increase `retries_on_schema_error` if needed.
- The `model_version` field in `Recommendation` is not populated for Ollama (Ollama
  does not expose a version string in its response).

## 9. Configuration Management

- Keep config in versioned yaml files.
- Include config version in run artifacts.
- Any runtime-affecting change requires changelog entry and review.
