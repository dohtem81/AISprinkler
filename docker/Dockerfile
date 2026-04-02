# =============================================================================
# AISprinkler – Multi-stage Dockerfile
# Stages:
#   base   – shared deps
#   app    – FastAPI service (target: app)
#   worker – Celery worker  (target: worker)
# =============================================================================

FROM python:3.12-slim AS base

WORKDIR /app

# System deps for psycopg / asyncpg build
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy source before editable install so package discovery succeeds.
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
RUN pip install --no-cache-dir -e .

# ── App stage ─────────────────────────────────────────────────────────────────
FROM base AS app

EXPOSE 8000

CMD ["uvicorn", "aisprinkler.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Worker stage ──────────────────────────────────────────────────────────────
FROM base AS worker

CMD ["celery", "-A", "aisprinkler.infrastructure.scheduler.celery_app", "worker", "--loglevel=info"]
