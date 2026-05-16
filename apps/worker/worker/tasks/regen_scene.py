"""Single-scene regeneration. Runs when the user edits a scene field
that invalidates its rendered assets (visual_prompt, has_speaker, etc.).
"""
from __future__ import annotations

from sqlalchemy import text

from worker import db
from worker.asset_urls import signed_url_for_asset
from worker.celery_app import celery_app
from worker.modal_client import (
    ffmpeg_composite,
    generate_voice,
    ltx_render,
    musetalk_sync,
    whisper_align,
)
from worker.sse import publish_event


def _fetch_scene(scene_id: str) -> dict | None:
    with db.session_scope() as s:
        row = s.execute(
            text("SELECT id, has_speaker FROM scenes WHERE id = :sid"),
            {"sid": scene_id},
        ).mappings().first()
        return dict(row) if row else None


@celery_app.task(name="worker.render.scene", bind=True, max_retries=2)
def regen_scene(self, project_id: str, scene_id: str,
                 idempotency_key: str | None = None) -> str:
    job_id = db.create_job(
        project_id=project_id,
        job_type="scene_regen",
        idempotency_key=idempotency_key or self.request.id,
    )
    project = db.fetch_project(project_id) or {}
    lang = project.get("active_language") or project.get("primary_language") or "en"
    scene = _fetch_scene(scene_id) or {}

    publish_event(project_id, "stage_change", {"stage": "scene", "scene_id": scene_id})
    ltx_render.remote(project_id=project_id, scene_id=scene_id)
    generate_voice.remote(project_id=project_id, scene_id=scene_id, language=lang)
    # Gate musetalk at the task level too — symmetric with render_project,
    # avoids paying container spin-up when there's no speaker.
    if scene.get("has_speaker"):
        musetalk_sync.remote(project_id=project_id, scene_id=scene_id,
                             language=lang, has_speaker=True)
    whisper_align.remote(project_id=project_id, scene_id=scene_id, language=lang)
    composite_result = ffmpeg_composite.remote(
        project_id=project_id, scene_id=scene_id, language=lang,
    )
    aid = composite_result.get("asset_id") if isinstance(composite_result, dict) else None

    db.update_job(job_id, status="succeeded", current_stage="done")
    publish_event(project_id, "scene_ready",
                  {"scene_id": scene_id, "kind": "composite",
                   "asset_id": aid, "asset_url": signed_url_for_asset(aid)})
    publish_event(project_id, "done", {"scene_id": scene_id})
    return job_id
