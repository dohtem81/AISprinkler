# AISprinkler (Design-Phase Repository)

This repository contains implementation-ready design documentation for AISprinkler.

Current phase scope is design only. No runtime services are implemented yet.

## Project Goal

AISprinkler starts from a daily preset irrigation schedule stored in a database, then adjusts the next 24 hours using weather context:

- Rain observed in last 24 hours
- Rain forecast for next 24 hours
- Deterministic safety and policy rules
- Confidence-gated AI recommendation

## Locked v1 Decisions

- Stack target: Python + FastAPI + PostgreSQL + Redis + Celery
- Scope target: single device only
- Decision gate: auto-apply above threshold, manual review below threshold
- Weather strategy: multi-provider with fallback
- Governance: internal auditability and traceability by default

## Document Map

- [Architecture](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [Orchestration Backbone](docs/ORCHESTRATION.md)
- [AI Agent Specification](docs/AI_AGENT_SPEC.md)
- [Prompts and Rules (Normative Policy Source)](docs/PROMPTS_AND_RULES.md)
- [LangChain Configuration Spec](docs/LANGCHAIN_CONFIG_SPEC.md)
- [Traceability Spec](docs/TRACEABILITY.md)
- [Risk Register](docs/RISK_REGISTER.md)
- [Assumptions](docs/ASSUMPTIONS.md)
- [Design Review Checklist](docs/DESIGN_REVIEW_CHECKLIST.md)
- [Implementation Readiness Checklist](docs/IMPLEMENTATION_READINESS.md)
- [Baseline Schedule – Alabama Best Practices](docs/BASELINE_SCHEDULE_ALABAMA.md)

## Config Examples

- [LangChain config example](config/langchain.config.example.yaml)
- [Scheduler config example](config/scheduler.config.example.yaml)
- [Rules policy example](config/rules.policy.example.yaml)

## Seed Data

- [Alabama baseline schedule (SQL)](config/seeds/alabama_baseline_schedule.sql)

## Source of Truth Rule

Thresholds and decision policy are normative in:

- [Prompts and Rules](docs/PROMPTS_AND_RULES.md)

Other documents reference this policy and must not redefine conflicting values.

## Intended Runtime Flow (Design)

1. Scheduler triggers a daily adjustment run.
2. Orchestrator collects baseline schedule + weather snapshots.
3. Agent generates a bounded recommendation.
4. Deterministic rule engine applies hard constraints.
5. Confidence gate chooses auto-apply or manual review path.
6. Execution adapter applies schedule to device and returns receipt.
7. Traceability artifacts are persisted for audit and replay.

## Not in v1

- Multi-device scheduling
- Zone-level optimization
- Autonomous model retraining
- Complex soil digital twin modeling
