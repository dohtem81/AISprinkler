"""Celery runtime configuration.

This module is loaded by ``celery_app`` via ``config_from_object``.
"""

from __future__ import annotations

import os

broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

timezone = "UTC"
enable_utc = True

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

task_track_started = True
task_acks_late = True
worker_prefetch_multiplier = 1

# Conservative defaults to avoid runaway retries.
task_default_retry_delay = 60
task_default_max_retries = 2