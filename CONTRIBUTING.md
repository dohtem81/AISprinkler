# Contributing

Thank you for contributing to AISprinkler.

## Development Principles

- Runtime and tests are Docker-only for this repository.
- Keep changes small, focused, and easy to review.
- Preserve Clean Architecture boundaries (domain/application/infrastructure separation).
- Prefer additive, non-destructive data changes unless explicitly approved.

## Prerequisites

- Docker Desktop (or compatible Docker Engine + Compose)
- GNU Make (optional but recommended)

## Local Workflow

1. Create a branch from `main`.
2. Build and start services.
3. Implement changes with tests.
4. Run quality checks.
5. Open a PR with clear summary and impact.

### Start Services

Using Make:

```bash
make up-all
```

Using Docker Compose directly:

```bash
docker compose -f docker/docker-compose.yml up -d
```

### Run Tests (Docker-only)

```bash
make test
make test-unit
make test-integration
make test-cov
```

Equivalent direct commands are in `README.md` and `Makefile`.

### Quality Checks

```bash
make lint
make fmt
make typecheck
```

## Coding Standards

- Python: 3.12+
- Linting: Ruff
- Typing: mypy (strict)
- Tests: pytest
- Keep comments concise and meaningful.
- Avoid unrelated refactors in the same PR.

## Database and Migrations

- Bootstrap currently handles additive schema synchronization for managed tables.
- If your change requires explicit migration behavior, document and include migration steps.
- Do not introduce destructive schema operations without a rollback plan.

## Observability and Auditability

When changing decision logic, scheduling, or weather ingestion:

- Preserve correlation-id-based traceability.
- Keep `agent_prompt_exchange` and run artifacts consistent.
- Update Grafana SQL/views and docs when behavior or fields change.

## Documentation Expectations

Update docs in the same PR when behavior changes, especially:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DATABASE_SCHEMA.md`
- `docs/ORCHESTRATION.md`
- `docs/TRACEABILITY.md`
- `CHANGELOG.md`

## Commit and PR Guidelines

- Use clear, imperative commit messages.
- Include why the change is needed, not only what changed.
- In PR description, include:
  - Scope and rationale
  - Risk and rollback notes
  - Test evidence (commands run)
  - Any config/env changes

## Pull Request Checklist

- [ ] Tests added or updated for changed behavior
- [ ] `make test` (or relevant subset) passes
- [ ] `make lint`, `make fmt`, and `make typecheck` pass
- [ ] Docs updated for user-visible or architectural changes
- [ ] `CHANGELOG.md` updated under `Unreleased`
- [ ] No secrets, generated binaries, or `__pycache__` files committed
