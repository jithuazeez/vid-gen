"""SSE event envelope.

Workers PUBLISH to Redis channel `project:<id>:events`. The API service
SUBSCRIBE per `/jobs/:id/events` and forwards.
"""
from typing import Any, Literal

from pydantic import BaseModel

EventName = Literal[
    # Chat
    "token",
    "slot_update",
    "question",
    "ready",
    # Render
    "stage_change",
    "scene_ready",
    "progress",
    "done",
    "error",
]


class SSEEvent(BaseModel):
    event: EventName
    data: dict[str, Any]
