#!/usr/bin/env python
"""Manually trigger a daily adjustment run for the configured device."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, datetime, timezone
from uuid import UUID

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    device_id_str = os.getenv("DEVICE_ID")
    if not device_id_str:
        logger.error("DEVICE_ID environment variable is required.")
        sys.exit(1)

    device_id = UUID(device_id_str)
    run_date = date.today()

    logger.info("Triggering daily adjustment for device=%s date=%s", device_id, run_date)

    from aisprinkler.application.dtos.adjustment_dtos import DailyAdjustmentRequest
    from aisprinkler.infrastructure.scheduler._di import build_use_case  # TODO: DI wiring

    request = DailyAdjustmentRequest(
        device_id=device_id,
        run_date=run_date,
        trigger_type="manual",
        as_of=datetime.now(timezone.utc),
    )
    use_case = build_use_case()
    result = await use_case.execute(request)
    logger.info(
        "Run complete: id=%s state=%s auto_applied=%s",
        result.run_id,
        result.final_state.value,
        result.auto_applied,
    )


if __name__ == "__main__":
    asyncio.run(main())
