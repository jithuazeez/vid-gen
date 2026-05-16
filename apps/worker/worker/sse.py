"""SSE publish helper for Celery tasks.

Workers PUBLISH JSON envelopes to `project:<project_id>:events`. The API
subscribes per `/jobs/:id/events` and forwards as SSE frames.
"""
from __future__ import annotations

import json
import os
from typing import Any

import redis

_redis: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return _redis


def publish_event(project_id: str, event: str, data: dict[str, Any]) -> None:
    payload = json.dumps({"event": event, "data": data})
    _client().publish(f"project:{project_id}:events", payload)
