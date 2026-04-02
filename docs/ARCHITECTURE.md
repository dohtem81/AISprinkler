# Architecture Specification

## 1. Purpose

Define component boundaries and data flow for AISprinkler, which adjusts daily irrigation duration using weather context while keeping deterministic safety controls.

## 2. v1 Scope Boundary

Included:

- Single irrigation device
- Daily baseline schedule persistence
- AI recommendation for next-run adjustment using recent observed weather and forecast context
- Deterministic rules and confidence gate
- Trigger and execution contract
- Full traceability

Excluded:

- Multiple devices
- Zone-level control
- Online reinforcement learning
- Dynamic soil sensor fusion outside basic optional field support

## 3. Component Model

### 3.1 Scheduler and Orchestrator

Responsibilities:

- Trigger daily run and optional event-driven reevaluation
- Trigger operational refresh runs and support replay/manual triggers
- Manage run state transitions
- Execute idempotent orchestration steps
- Handle retries, fallback, and escalation

### 3.2 Weather Integration Layer

Responsibilities:

- Pull weather from primary provider
- Fallback to secondary provider on failure or stale data
- Normalize observations and forecasts
- Persist snapshot used for decision
- Refresh future forecast horizon (next 7 days) on each pull for consistent observability

### 3.3 AI Decision Agent

Responsibilities:

- Consume baseline schedule + normalized weather + policy context
- Produce structured recommendation with rationale and confidence
- Stay inside deterministic bounds defined in policy
- Avoid example-copy behavior through explicit prompt constraints and output validation/coercion

Implementation: `LangChainAgentAdapter` (`infrastructure/agent/langchain_agent.py`).

Prompt/rules source: `config/SPRINKLER_LLM_RULES.md`.

LLM provider is **runtime-configurable** via the `LLM_PROVIDER` environment variable:

| Provider | Value | Notes |
|---|---|---|
| OpenAI (default) | `openai` | Requires `OPENAI_API_KEY` |
| Anthropic | `anthropic` | Requires `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama` | No API key; set `OLLAMA_BASE_URL` |

Model name is further overridable via `LLM_MODEL`. See `docs/LANGCHAIN_CONFIG_SPEC.md §9`.

### 3.4 Deterministic Rule Engine

Responsibilities:

- Enforce hard constraints independent of LLM
- Clamp or override recommendation when required
- Record which rules were applied

### 3.5 Execution Adapter

Responsibilities:

- Convert approved schedule into device command schema
- Apply command with timeout/retry contract
- Return execution receipt including proof fields

### 3.6 Persistence Layer

Responsibilities:

- Store schedules, weather, recommendations, executions, and audit events
- Guarantee immutable decision snapshots and append-only audit log behavior

## 4. High-Level Flow

1. Run is created by scheduler and assigned correlation id.
2. Baseline schedule and weather context are loaded.
3. Agent proposes bounded action: keep, reduce, skip, or increase.
4. Rule engine evaluates hard constraints and finalizes proposal.
5. Confidence gate selects auto-apply or manual-review path.
6. Approved command is sent to execution adapter.
7. Receipt and all trace artifacts are persisted.

Run state names and valid transitions for each step above are defined in
`docs/ORCHESTRATION.md §3` (10 states: queued → collecting_data → reasoning →
rule_check → approval_gate → dispatching → verifying → closed | failed | manual_review).

## 5. Runtime Responsibility Split

- LLM decides recommendation inside policy envelope.
- Rule engine has final authority on safety constraints.
- Confidence gate controls autonomous vs review path.
- Orchestrator controls state, retries, and completion semantics.

## 6. Non-Functional Targets (Design)

- Reproducibility: same inputs and same policy produce same final action.
- Explainability: every run stores rationale, rule set, and applied constraints.
- Resilience: failures degrade to baseline schedule when safe.
- Operability: each run is traceable end to end with one correlation id.

## 7. Architecture Decisions

- Decision A1: Single-device v1 simplifies orchestration and traceability.
- Decision A2: Deterministic rule layer is mandatory to bound LLM behavior.
- Decision A3: Fallback weather provider is mandatory for run continuity.
- Decision A4: Confidence-gated automation reduces risk while preserving autonomy.
