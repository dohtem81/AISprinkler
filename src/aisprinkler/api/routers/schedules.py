"""Schedules router – manage baseline schedules."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_schedules(device_id: UUID) -> dict[str, object]:
    # TODO: query schedule repository
    return {"device_id": str(device_id), "status": "not_implemented"}
