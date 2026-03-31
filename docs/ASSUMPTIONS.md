# Assumptions

## Product Assumptions

- Irrigation baseline schedule exists before AI adjustment is attempted.
- Water optimization objective is balanced with plant safety objective.
- Human operators are available to process manual review queue.

## Technical Assumptions

- PostgreSQL is available for primary persistence.
- Redis is available for queueing and transient orchestration state.
- Weather providers expose required fields for 24-hour forecast and recent rain.

## Operational Assumptions

- Daily adjustment run executes before irrigation start window.
- Device adapter supports idempotent command behavior.
- System clocks and timezone configuration are consistent.

## Governance Assumptions

- Policy and prompt versions are controlled and recorded.
- Audit retention windows are acceptable for internal operations.

## Scope Assumptions

- v1 handles one device only.
- Zone-level logic is deferred to post-v1.
