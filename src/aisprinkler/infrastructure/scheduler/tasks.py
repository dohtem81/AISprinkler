"""Celery scheduled tasks."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from aisprinkler.infrastructure.scheduler.celery_app import app

logger = logging.getLogger(__name__)


@app.task(
    name="aisprinkler.daily_adjustment",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def daily_adjustment_task(self: object, device_id: str, run_date_iso: str) -> dict[str, object]:
    """Trigger one daily adjustment run for a device.

    Scheduled via Celery Beat at 06:00 local time (configured in scheduler.config.example.yaml).
    """
    import asyncio  # noqa: PLC0415

    from aisprinkler.application.dtos.adjustment_dtos import DailyAdjustmentRequest
    from aisprinkler.infrastructure.scheduler._di import build_use_case  # TODO: DI wiring

    try:
        run_date = date.fromisoformat(run_date_iso)
        request = DailyAdjustmentRequest(
            device_id=UUID(device_id),
            run_date=run_date,
            trigger_type="daily",
            as_of=datetime.now(timezone.utc),
        )
        use_case = build_use_case()
        result = asyncio.run(use_case.execute(request))
        logger.info(
            "daily_adjustment_task completed",
            extra={"run_id": str(result.run_id), "state": result.final_state.value},
        )
        return {"run_id": str(result.run_id), "state": result.final_state.value}
    except Exception as exc:
        logger.exception("daily_adjustment_task failed: %s", exc)
        raise self.retry(exc=exc)  # type: ignore[attr-defined]
