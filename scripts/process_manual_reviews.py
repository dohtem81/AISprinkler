#!/usr/bin/env python
"""Process all pending manual review runs in the queue."""

from __future__ import annotations

import asyncio
import logging
import os

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    # TODO: load pending runs from repository and dispatch to ProcessManualReviewUseCase
    logger.info("Checking manual review queue...")
    raise NotImplementedError("process_manual_reviews is not yet wired to the DI container.")


if __name__ == "__main__":
    asyncio.run(main())
