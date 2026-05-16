"""Day-1 vertical slice: browser → API → Celery → Modal → SSE → browser."""
from __future__ import annotations

from worker.celery_app import celery_app
from worker.modal_client import ping as modal_ping
from worker.sse import publish_event


@celery_app.task(name="worker.ping")
def ping(project_id: str) -> dict:
    publish_event(project_id, "stage_change", {"stage": "ping", "from": "celery"})
    result = modal_ping.remote(project_id)
    publish_event(project_id, "done", {"from": "celery", "modal_result": result})
    return {"ok": True, "modal": result}
