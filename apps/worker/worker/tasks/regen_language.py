"""Cheap language switch — reuses cached visuals + native audio.

Architecture.md §10. ~10–20% of initial render cost per added language.
Same per-scene order as render_project, gated on `has_speaker`: speaker
scenes run voice → lipsync → subs → composite; non-speaker scenes go
straight to composite (LTX-2's native audio is language-agnostic).
"""
from __future__ import annotations

from sqlalchemy import text

from worker import db
from worker.asset_urls import signed_url_for_asset
from worker.celery_app import celery_app
from worker.modal_client import (
    ffmpeg_composite,
    final_export,
    generate_voice,
    musetalk_sync,
    whisper_align,
)
from worker.sse import publish_event


def _record_calls(job_id: str, calls: dict[str, list[str]]) -> None:
    if not calls:
        return
    import json as _json
    with db.session_scope() as s:
        s.execute(
            text(
                "UPDATE render_jobs "
                "SET modal_call_ids = COALESCE(modal_call_ids, '{}'::jsonb) "
                "                     || CAST(:c AS jsonb), "
                "    updated_at = now() "
                "WHERE id = :jid"
            ),
            {"jid": job_id, "c": _json.dumps(calls)},
        )


def _call_id(call: object) -> str | None:
    return getattr(call, "object_id", None) or getattr(call, "id", None)


@celery_app.task(name="worker.render.language", bind=True, max_retries=2)
def regen_language(self, project_id: str, language: str,
                   idempotency_key: str | None = None,
                   job_id: str | None = None) -> str | None:
    project = db.fetch_project(project_id)
    if project is None:
        raise RuntimeError("project not found")

    if language in (project.get("available_languages") or []):
        with db.session_scope() as s:
            s.execute(
                text("UPDATE projects SET active_language = :l, updated_at = now() "
                     "WHERE id = :pid"),
                {"l": language, "pid": project_id},
            )
        publish_event(project_id, "done", {"language": language, "instant": True})
        return None

    # API pre-creates the RenderJob row (so /jobs/:id/events resolves
    # immediately); fall back to creating one here if invoked directly.
    if job_id:
        db.start_job(job_id)
    else:
        job_id = db.create_job(
            project_id=project_id,
            job_type="language_render",
            language=language,
            idempotency_key=idempotency_key or self.request.id,
        )

    try:
        scenes = db.list_scenes(project_id)
        publish_event(project_id, "stage_change", {"stage": "voice", "language": language})

        composite_calls = []
        for s in scenes:
            sid = str(s["id"])

            if s.get("has_speaker"):
                generate_voice.spawn(project_id=project_id, scene_id=sid, language=language).get()
                publish_event(project_id, "asset_progress",
                              {"asset_type": "voice", "scene_id": sid, "language": language, "percent": 100})

                musetalk_sync.spawn(project_id=project_id, scene_id=sid,
                                    language=language, has_speaker=True).get()
                publish_event(project_id, "asset_progress",
                              {"asset_type": "lipsync_video", "scene_id": sid,
                               "language": language, "percent": 100})

                whisper_align.spawn(project_id=project_id, scene_id=sid, language=language).get()
                publish_event(project_id, "asset_progress",
                              {"asset_type": "subtitle_srt", "scene_id": sid,
                               "language": language, "percent": 100})

            composite_calls.append((sid, ffmpeg_composite.spawn(
                project_id=project_id, scene_id=sid, language=language,
            )))

        _record_calls(job_id, {
            "ffmpeg_composite": [c for c in (_call_id(call) for _, call in composite_calls) if c],
        })

        for sid, call in composite_calls:
            result = call.get()
            aid = result.get("asset_id") if isinstance(result, dict) else None
            publish_event(project_id, "scene_ready",
                          {"scene_id": sid, "kind": "composite", "language": language,
                           "asset_id": aid, "asset_url": signed_url_for_asset(aid)})

        publish_event(project_id, "stage_change", {"stage": "export", "language": language})
        export_result = final_export.remote(
            project_id=project_id, language=language,
            quality="1080p", subtitles_mode="burned",
        )
        db.append_available_language(project_id, language)
        export_asset_id = export_result.get("asset_id") if isinstance(export_result, dict) else None
        db.update_job(
            job_id, status="succeeded", current_stage="done",
            progress={"percent": 100, "final_export_asset_id": export_asset_id},
        )
        publish_event(project_id, "done", {"language": language, "export": export_result,
                                           "final_export_asset_id": export_asset_id})
        return job_id
    except Exception as e:
        # Surface failure to the editor instead of leaving the job pending
        # forever. The frontend listens for `pipeline_failed` and shows it
        # in the activity log.
        err = f"{type(e).__name__}: {e}"
        try:
            db.update_job(job_id, status="failed", current_stage="error",
                          progress={"error": err}, error=err)
        except Exception:
            pass
        publish_event(project_id, "pipeline_failed",
                      {"language": language, "error": err, "job_id": job_id})
        raise
