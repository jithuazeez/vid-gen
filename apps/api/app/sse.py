"""SSE pub/sub bridge.

Workers (Modal functions) publish JSON events to Redis channel
`project:<project_id>:events`. The API service subscribes per
`/jobs/:id/events` and forwards via Server-Sent Events.

This is the *only* role Redis plays — there is no broker, no result backend.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.settings import get_settings

log = structlog.get_logger()
settings = get_settings()

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def channel_for(project_id: str) -> str:
    return f"project:{project_id}:events"


async def publish_event(project_id: str, event: str, data: dict[str, Any]) -> None:
    """Publish a single SSE event. Called from Modal workers via Redis."""
    payload = json.dumps({"event": event, "data": data})
    await get_redis().publish(channel_for(project_id), payload)


async def subscribe_events(project_id: str) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to a project's event channel. Yields parsed event dicts.

    The caller is responsible for formatting these as SSE frames.
    """
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(channel_for(project_id))
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                yield json.loads(message["data"])
            except json.JSONDecodeError:
                log.warning("bad_sse_payload", raw=message["data"])
    finally:
        await pubsub.unsubscribe(channel_for(project_id))
        await pubsub.close()
