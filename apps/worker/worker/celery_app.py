"""Celery app for the pipeline orchestrator.

Broker = Redis (shared with the API for SSE pub/sub — different keys though).
Workers should be started with::

    celery -A worker.celery_app worker --concurrency=4 --loglevel=INFO

Tasks are imported lazily so this module stays cheap to import.
"""
from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "vidplatform",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "worker.tasks.ping",
        "worker.tasks.storyboard",
        "worker.tasks.render_project",
        "worker.tasks.regen_language",
        "worker.tasks.regen_scene",
        "worker.tasks.export",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Long pipeline tasks; the soft limit gives us a chance to clean up.
    task_soft_time_limit=1500,
    task_time_limit=1800,
    broker_connection_retry_on_startup=True,
)
