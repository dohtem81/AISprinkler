"""Celery application factory."""

from __future__ import annotations

from celery import Celery

app = Celery("aisprinkler")
app.config_from_object("aisprinkler.infrastructure.scheduler.celery_config")
app.autodiscover_tasks(["aisprinkler.infrastructure.scheduler"])
