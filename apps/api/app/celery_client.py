"""Thin Celery client for the API process.

We do *not* import the worker package here — the API enqueues by task
name so the two services can be deployed independently.
"""
from __future__ import annotations

from typing import Any

from celery import Celery

from app.settings import get_settings

_settings = get_settings()

celery_client = Celery("vidplatform-client", broker=_settings.redis_url, backend=_settings.redis_url)
celery_client.conf.update(task_serializer="json", accept_content=["json"])


def send(task_name: str, *args: Any, **kwargs: Any) -> str:
    res = celery_client.send_task(task_name, args=list(args), kwargs=kwargs)
    return res.id
