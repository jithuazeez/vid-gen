"""Final export task — separate from `render_project` so users can
re-export at different quality / subtitle settings without re-rendering.
"""
from __future__ import annotations

from worker import db
from worker.celery_app import celery_app
from worker.modal_client import final_export
from worker.sse import publish_event


@celery_app.task(name="worker.export.run", bind=True, max_retries=2)
def export(self, project_id: str, language: str, quality: str = "1080p",
           subtitles: str = "burned", idempotency_key: str | None = None,
           job_id: str | None = None) -> str:
    if job_id:
        db.start_job(job_id)
    else:
        job_id = db.create_job(
            project_id=project_id,
            job_type="export",
            language=language,
            idempotency_key=idempotency_key or self.request.id,
        )
    publish_event(project_id, "stage_change", {"stage": "export"})
    result = final_export.remote(
        project_id=project_id, language=language,
        quality=quality, subtitles_mode=subtitles,
    )
    asset_id = result.get("asset_id") if isinstance(result, dict) else None
    progress = {"final_export_asset_id": asset_id} if asset_id else {}
    db.update_job(job_id, status="succeeded", current_stage="done", progress=progress)
    publish_event(project_id, "done", {"export": result, "language": language,
                                       "final_export_asset_id": asset_id})
    db.set_project_status(project_id, "completed")
    return job_id
