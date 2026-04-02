#!/usr/bin/env python
"""Manually trigger a daily adjustment run for the configured device."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    device_id_str = os.getenv("DEVICE_ID")
    if not device_id_str:
        logger.error("DEVICE_ID environment variable is required.")
        sys.exit(1)

    device_id = UUID(device_id_str)

    run_date_env = os.getenv("RUN_DATE")
    lookahead_days = int(os.getenv("RUN_DATE_LOOKAHEAD_DAYS", "7"))

    if run_date_env:
        try:
            run_date = date.fromisoformat(run_date_env)
        except ValueError:
            logger.error("RUN_DATE must be YYYY-MM-DD, got: %s", run_date_env)
            sys.exit(1)
    else:
        run_date = date.today()
        from aisprinkler.infrastructure.persistence.bootstrap import bootstrap_database
        from aisprinkler.infrastructure.persistence.db import get_session_factory
        from aisprinkler.infrastructure.persistence.schedule_repo import SqlAlchemyScheduleRepository

        # Ensure baseline tables/views exist before probing schedule availability.
        await bootstrap_database()
        session_factory = get_session_factory()
        async with session_factory() as session:
            schedule_repo = SqlAlchemyScheduleRepository(session)
            for offset in range(max(lookahead_days, 1)):
                candidate = date.today() + timedelta(days=offset)
                slots = await schedule_repo.get_active_for_date(device_id, candidate)
                if slots:
                    run_date = candidate
                    break

        if run_date != date.today():
            logger.info(
                "No active schedule today; selected next scheduled date %s (lookahead=%s days)",
                run_date,
                lookahead_days,
            )

    logger.info("Triggering daily adjustment for device=%s date=%s", device_id, run_date)

    from aisprinkler.application.dtos.adjustment_dtos import DailyAdjustmentRequest
    from aisprinkler.infrastructure.scheduler._di import execute_daily_adjustment

    request = DailyAdjustmentRequest(
        device_id=device_id,
        run_date=run_date,
        trigger_type="manual",
        as_of=datetime.now(timezone.utc),
    )
    result = await execute_daily_adjustment(request)
    logger.info(
        "Run complete: id=%s state=%s auto_applied=%s",
        result.run_id,
        result.final_state.value,
        result.auto_applied,
    )


if __name__ == "__main__":
    asyncio.run(main())
