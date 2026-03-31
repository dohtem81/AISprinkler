#!/usr/bin/env python
"""Retry a single failed run by run_id."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from uuid import UUID

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: retry_failed_run.py <run_id>")
        sys.exit(1)

    run_id = UUID(sys.argv[1])
    logger.info("Retrying run %s", run_id)
    # TODO: load run from repository, reset state to queued, re-dispatch use case
    raise NotImplementedError("retry_failed_run is not yet wired to the DI container.")


if __name__ == "__main__":
    asyncio.run(main())
