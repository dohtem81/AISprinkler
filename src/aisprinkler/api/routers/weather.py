"""Weather router – refresh forecast data used by the backend."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aisprinkler.infrastructure.persistence.db import get_db_session
from aisprinkler.infrastructure.scheduler._di import refresh_weather_forecast

router = APIRouter()


class RefreshWeatherForecastRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=7)
    device_id: UUID | None = None


@router.post("/refresh")
async def refresh_forecast(
    body: RefreshWeatherForecastRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    request = body or RefreshWeatherForecastRequest()
    try:
        result = await refresh_weather_forecast(
            session,
            days=request.days,
            device_id=request.device_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    return {
        "status": "refreshed",
        "provider": result.provider,
        "days": result.days,
        "rows_fetched": result.rows_fetched,
        "rows_persisted": result.rows_persisted,
        "location_id": str(result.location_id),
        "zipcode": result.zipcode,
        "city": result.city,
        "state_code": result.state_code,
        "fetched_at": result.fetched_at.isoformat(),
    }
