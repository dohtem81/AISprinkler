"""Runs router – trigger and inspect adjustment runs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def trigger_run(device_id: UUID, run_date: str) -> dict[str, object]:
    # TODO: wire RunDailyAdjustmentUseCase via dependency injection
    return {"status": "not_implemented"}


@router.get("/{run_id}")
async def get_run(run_id: UUID) -> dict[str, object]:
    # TODO: query run repository
    return {"run_id": str(run_id), "status": "not_implemented"}


@router.get("/{run_id}/manual-review")
async def get_manual_review(run_id: UUID) -> dict[str, object]:
    # TODO: return runs in manual_review state
    return {"run_id": str(run_id), "status": "not_implemented"}


@router.post("/{run_id}/manual-review/approve")
async def approve_review(run_id: UUID) -> dict[str, object]:
    # TODO: wire ProcessManualReviewUseCase
    return {"run_id": str(run_id), "status": "not_implemented"}
