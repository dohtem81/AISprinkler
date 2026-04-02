"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from aisprinkler.api.routers import runs, schedules
from aisprinkler.infrastructure.logging_config import configure_logging
from aisprinkler.infrastructure.persistence.bootstrap import bootstrap_database
from aisprinkler.infrastructure.persistence.db import dispose_engine


configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await bootstrap_database()
    try:
        yield
    finally:
        await dispose_engine()

app = FastAPI(
    title="AISprinkler API",
    description="AI-driven irrigation schedule optimizer",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["schedules"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
