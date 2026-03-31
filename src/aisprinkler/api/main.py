"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from aisprinkler.api.routers import runs, schedules

app = FastAPI(
    title="AISprinkler API",
    description="AI-driven irrigation schedule optimizer",
    version="0.1.0",
)

app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["schedules"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
