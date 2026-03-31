# Design Review Checklist

Last reviewed: 2026-03-30

Legend: [x] covered  [~] partial gap  [ ] open

## Coverage

- [x] Database schema covers schedules, weather, decisions, execution, and audit.
      → DATABASE_SCHEMA.md: device, baseline_schedule, weather_observation,
        weather_forecast_snapshot, adjustment_run, agent_recommendation,
        rule_evaluation, final_schedule_adjustment, execution_receipt, audit_event.
- [x] Orchestration state machine and retry behavior are documented.
      → ORCHESTRATION.md §3 state machine (10 states), §6 retry matrix.
- [x] AI output schema is strict and parseable.
      → AI_AGENT_SPEC.md §4 (7 required JSON fields), PROMPTS_AND_RULES.md §7.4.
- [x] Confidence gate behavior is explicit.
      → PROMPTS_AND_RULES.md §6 (normative), ORCHESTRATION.md §5 (references it).
- [x] Trigger and adapter command contract is documented.
      → ORCHESTRATION.md §8 (command payload + response payload schemas).
- [x] Traceability artifacts are mandatory and complete.
      → TRACEABILITY.md §3 (5 artifact types), §4 (8 required audit events).

## Consistency

- [x] Threshold values match normative policy source.
      → All threshold values live only in PROMPTS_AND_RULES.md §2.
        ORCHESTRATION.md §5 references the policy doc instead of re-stating values.
- [x] Action vocabulary is consistent across all docs.
      → keep|reduce|skip|increase used identically in AI_AGENT_SPEC.md,
        ORCHESTRATION.md, PROMPTS_AND_RULES.md, and config files.
- [~] Run states are identical across architecture and orchestration docs.
- [x] Run states are identical across architecture and orchestration docs.
                  → ORCHESTRATION.md §3 is the normative state list (10 states).
                        ARCHITECTURE.md §4 now cross-references ORCHESTRATION.md §3 with all
                        10 state names enumerated.
- [x] Policy and prompt versioning strategy is consistent.
      → PROMPTS_AND_RULES.md §8 defines both version formats.
        LANGCHAIN_CONFIG_SPEC.md §9 and AI_AGENT_SPEC.md §10 reference them.

## Resilience

- [x] Weather fallback path is documented.
      → ARCHITECTURE.md §3.2, ORCHESTRATION.md §6, LANGCHAIN_CONFIG_SPEC.md §8.
- [x] Model fallback path is documented.
      → LANGCHAIN_CONFIG_SPEC.md §2 (fallback model profile) and §8.
- [x] Safe baseline fallback is documented.
      → ORCHESTRATION.md §9, PROMPTS_AND_RULES.md §4 rule 4,
        scheduler.config.example.yaml fallbacks block.
- [x] Manual review escalation path is documented.
      → ORCHESTRATION.md §3 (manual_review state) and §5,
        AI_AGENT_SPEC.md §8, scheduler config queue definition.

## Operability

- [x] Minimum metrics set is defined.
      → TRACEABILITY.md §5: 7 named metrics.
- [x] Audit query requirements are defined.
      → TRACEABILITY.md §7: 4 required operational query patterns.
- [x] Correlation id propagation points are defined.
      → TRACEABILITY.md §2: 6 named propagation points.
- [ ] Alert thresholds are numerically defined.
- [x] Alert thresholds are numerically defined.
                  → TRACEABILITY.md §5.1 now contains a 6-row table with numeric trigger
                        conditions and severity levels for every metric in §5.

## Sign-off

- [ ] Product sign-off
- [ ] Backend sign-off
- [ ] AI/ML sign-off
- [ ] Operations sign-off
