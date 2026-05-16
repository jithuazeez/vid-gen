"""Phase B controller: full render of the primary language.

Architecture.md §8 DAG. Per scene: voice → (gated)lipsync → subtitles → composite.
We await whisper_align before composite because composite burns in the SRT.

Every Modal call is logged with stage + scene + call_id on entry, exit, and
exception. On failure: the job row is marked `failed` with a structured error
message, an `error` SSE event is published, and the exception re-raises so
Celery records the traceback.
"""
from __future__ import annotations

import os
import time
import traceback

import structlog
from sqlalchemy import text

from worker import db
from worker.asset_urls import signed_url_for_asset
from worker.celery_app import celery_app
from worker import manifest
from worker.modal_client import (
    acestep_music,
    ffmpeg_composite,
    final_export,
    generate_voice,
    ltx_render,
    musetalk_sync,
    whisper_align,
)
from worker.sse import publish_event

log = structlog.get_logger(__name__)


def _record_modal_calls(job_id: str, calls: dict[str, list[str]]) -> None:
    """Persist Modal FunctionCall ids on render_jobs.modal_call_ids so a
    cancellation request can reach Modal. Architecture.md §8."""
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


def _await(
    call,
    *,
    stage: str,
    project_id: str,
    job_id: str,
    scene_id: str | None = None,
    extra: dict | None = None,
):
    """Await a Modal FunctionCall with structured logging + failure handling.

    Logs entry/exit/duration. On exception: records error on job, emits an
    SSE `error` event with full context, and re-raises so Celery sees it.
    """
    cid = _call_id(call)
    ctx = {
        "stage": stage,
        "project_id": project_id,
        "job_id": job_id,
        "scene_id": scene_id,
        "modal_call_id": cid,
        **(extra or {}),
    }
    log.info("modal.await.start", **ctx)
    db.update_job(job_id, current_stage=stage)
    t0 = time.monotonic()
    try:
        result = call.get()
    except Exception as e:
        dur = time.monotonic() - t0
        tb = traceback.format_exc()
        log.error("modal.await.failed", duration_s=round(dur, 2),
                  error=str(e), error_type=type(e).__name__, traceback=tb, **ctx)
        err_msg = f"{stage} failed" + (f" (scene {scene_id})" if scene_id else "") \
                  + f": {type(e).__name__}: {e}"
        try:
            db.update_job(job_id, status="failed", current_stage=stage,
                          error=err_msg[:4000])
            db.set_project_status(project_id, "failed")
        except Exception:
            log.exception("job.fail_record_failed", **ctx)
        publish_event(project_id, "error", {
            "stage": stage, "scene_id": scene_id, "modal_call_id": cid,
            "error_type": type(e).__name__, "message": str(e),
        })
        raise
    dur = time.monotonic() - t0
    log.info("modal.await.ok", duration_s=round(dur, 2),
             result_keys=list(result.keys()) if isinstance(result, dict) else None,
             **ctx)
    return result


@celery_app.task(name="worker.render.project", bind=True, max_retries=2)
def render_project(self, project_id: str, language: str | None = None,
                   idempotency_key: str | None = None,
                   job_id: str | None = None) -> str:
    project = db.fetch_project(project_id)
    if project is None:
        raise RuntimeError("project not found")
    lang = language or project.get("primary_language") or "en"

    if job_id:
        db.start_job(job_id)
    else:
        job_id = db.create_job(
            project_id=project_id,
            job_type="initial_render",
            language=lang,
            idempotency_key=idempotency_key or self.request.id,
        )
    db.set_project_status(project_id, "rendering")

    log.info("render.start", project_id=project_id, job_id=job_id, language=lang,
             celery_task_id=self.request.id)

    scenes = db.list_scenes(project_id)
    log.info("render.scenes_loaded", project_id=project_id, job_id=job_id,
             scene_count=len(scenes),
             scene_ids=[str(s["id"]) for s in scenes])

    try:
        # ─── Phase B-1: visuals (LTX) + music (ACE-Step) in parallel ────
        publish_event(project_id, "stage_change", {"stage": "scenes"})
        db.update_job(job_id, current_stage="scenes")
        log.info("phase.b1.start", project_id=project_id, job_id=job_id)

        visual_calls = []
        for s in scenes:
            sid = str(s["id"])
            if s.get("scene_video_asset_id"):
                log.info("ltx.skip_already_done", project_id=project_id,
                         scene_id=sid, asset_id=s.get("scene_video_asset_id"))
                continue
            h = manifest.scene_video_hash({**s, "seed": project.get("seed")})
            if manifest.is_cached(h):
                log.info("ltx.cache_hit", project_id=project_id, scene_id=sid, hash=h)
                publish_event(project_id, "scene_ready",
                              {"scene_id": sid, "kind": "scene_video",
                               "cache_hit": True,
                               "asset_url": signed_url_for_asset(s.get("scene_video_asset_id"))})
                continue
            call = ltx_render.spawn(project_id=project_id, scene_id=sid)
            log.info("ltx.spawn", project_id=project_id, scene_id=sid,
                     modal_call_id=_call_id(call))
            visual_calls.append((s, call))

        music_call = None
        music_disabled = os.environ.get("MUSIC_DISABLE") == "1"
        if project.get("music_enabled") and not music_disabled:
            publish_event(project_id, "stage_change", {"stage": "music"})
            music_call = acestep_music.spawn(project_id=project_id)
            log.info("acestep.spawn", project_id=project_id,
                     modal_call_id=_call_id(music_call))
        elif music_disabled:
            log.info("acestep.skipped_by_env", project_id=project_id)

        _record_modal_calls(job_id, {
            "ltx_render":    [c for c in (_call_id(call) for _, call in visual_calls) if c],
            "acestep_music": [c for c in [_call_id(music_call)] if c] if music_call else [],
        })

        for scene, call in visual_calls:
            sid = str(scene["id"])
            result = _await(call, stage="ltx_render", project_id=project_id,
                            job_id=job_id, scene_id=sid)
            aid = result.get("asset_id") if isinstance(result, dict) else None
            publish_event(project_id, "scene_ready",
                          {"scene_id": sid, "kind": "scene_video",
                           "asset_id": aid, "asset_url": signed_url_for_asset(aid)})
        if music_call is not None:
            # Music is optional content. If acestep dies, log the failure
            # loudly but keep rendering — a video without background music
            # is still a valid result.
            try:
                _await(music_call, stage="acestep_music",
                       project_id=project_id, job_id=job_id)
            except Exception as e:
                log.warning("acestep.failed_continuing_without_music",
                            project_id=project_id, job_id=job_id,
                            error=str(e), error_type=type(e).__name__)
                publish_event(project_id, "warning", {
                    "stage": "acestep_music",
                    "message": "music generation failed — continuing without music",
                    "error_type": type(e).__name__,
                })
        publish_event(project_id, "progress", {"percent": 40})
        log.info("phase.b1.done", project_id=project_id, job_id=job_id)

        # ─── Phase B-2: per-scene language pipeline ─────────────────────
        publish_event(project_id, "stage_change", {"stage": "voice"})
        log.info("phase.b2.start", project_id=project_id, job_id=job_id,
                 language=lang, scene_count=len(scenes))
        composite_calls = []
        total = max(1, len(scenes))
        for idx, s in enumerate(scenes):
            sid = str(s["id"])
            log.info("scene.pipeline.start", project_id=project_id, job_id=job_id,
                     scene_id=sid, scene_index=idx)

            vc = generate_voice.spawn(project_id=project_id, scene_id=sid, language=lang)
            log.info("voice.spawn", project_id=project_id, scene_id=sid,
                     modal_call_id=_call_id(vc))
            _await(vc, stage="voice", project_id=project_id, job_id=job_id,
                   scene_id=sid, extra={"language": lang})
            publish_event(project_id, "asset_progress",
                          {"asset_type": "voice", "scene_id": sid, "percent": 100})

            if s.get("has_speaker"):
                ls = musetalk_sync.spawn(project_id=project_id, scene_id=sid,
                                          language=lang, has_speaker=True)
                log.info("musetalk.spawn", project_id=project_id, scene_id=sid,
                         modal_call_id=_call_id(ls))
                _await(ls, stage="musetalk_sync", project_id=project_id,
                       job_id=job_id, scene_id=sid, extra={"language": lang})
                publish_event(project_id, "asset_progress",
                              {"asset_type": "lipsync_video", "scene_id": sid, "percent": 100})
            else:
                log.info("musetalk.skip_no_speaker", project_id=project_id, scene_id=sid)

            sub = whisper_align.spawn(project_id=project_id, scene_id=sid, language=lang)
            log.info("whisper.spawn", project_id=project_id, scene_id=sid,
                     modal_call_id=_call_id(sub))
            _await(sub, stage="whisper_align", project_id=project_id,
                   job_id=job_id, scene_id=sid, extra={"language": lang})
            publish_event(project_id, "asset_progress",
                          {"asset_type": "subtitle_srt", "scene_id": sid, "percent": 100})

            cc = ffmpeg_composite.spawn(project_id=project_id, scene_id=sid, language=lang)
            log.info("composite.spawn", project_id=project_id, scene_id=sid,
                     modal_call_id=_call_id(cc))
            composite_calls.append((sid, cc))

            # Per-scene fine-grained progress so the UI bar moves between 40-90.
            pct = 40 + int(50 * (idx + 1) / total * 0.5)  # voice/lipsync/subs half
            publish_event(project_id, "progress", {"percent": pct})

        _record_modal_calls(job_id, {
            "ffmpeg_composite": [c for c in (_call_id(call) for _, call in composite_calls) if c],
        })

        for i, (sid, call) in enumerate(composite_calls):
            result = _await(call, stage="ffmpeg_composite", project_id=project_id,
                            job_id=job_id, scene_id=sid, extra={"language": lang})
            aid = result.get("asset_id") if isinstance(result, dict) else None
            publish_event(project_id, "scene_ready",
                          {"scene_id": sid, "kind": "composite",
                           "asset_id": aid, "asset_url": signed_url_for_asset(aid)})
            pct = 65 + int(25 * (i + 1) / total)
            publish_event(project_id, "progress", {"percent": pct})
        publish_event(project_id, "progress", {"percent": 90})
        log.info("phase.b2.done", project_id=project_id, job_id=job_id)

        # ─── Phase B-3: final export ────────────────────────────────────
        publish_event(project_id, "stage_change", {"stage": "export"})
        db.update_job(job_id, current_stage="export")
        log.info("phase.b3.start", project_id=project_id, job_id=job_id,
                 quality="1080p", subtitles_mode="burned")
        t0 = time.monotonic()
        try:
            export_result = final_export.remote(
                project_id=project_id, language=lang,
                quality="1080p", subtitles_mode="burned",
            )
        except Exception as e:
            log.error("final_export.failed", project_id=project_id, job_id=job_id,
                      error=str(e), error_type=type(e).__name__,
                      traceback=traceback.format_exc())
            db.update_job(job_id, status="failed", current_stage="export",
                          error=f"final_export: {type(e).__name__}: {e}"[:4000])
            db.set_project_status(project_id, "failed")
            publish_event(project_id, "error", {
                "stage": "final_export", "error_type": type(e).__name__,
                "message": str(e),
            })
            raise
        log.info("phase.b3.done", project_id=project_id, job_id=job_id,
                 duration_s=round(time.monotonic() - t0, 2),
                 result_keys=list(export_result.keys()) if isinstance(export_result, dict) else None)

        export_asset_id = export_result.get("asset_id") if isinstance(export_result, dict) else None
        db.update_job(
            job_id, status="succeeded", current_stage="done",
            progress={"percent": 100, "final_export_asset_id": export_asset_id},
        )
        db.set_project_status(project_id, "ready")
        db.append_available_language(project_id, lang)
        publish_event(project_id, "done", {"language": lang, "export": export_result,
                                           "final_export_asset_id": export_asset_id})
        log.info("render.done", project_id=project_id, job_id=job_id,
                 final_export_asset_id=export_asset_id)
        return job_id

    except Exception:
        # _await + final_export branch already record the structured error;
        # this is the catch-all for anything else (e.g. db helper raising).
        log.exception("render.unhandled", project_id=project_id, job_id=job_id)
        try:
            db.update_job(job_id, status="failed",
                          error=traceback.format_exc()[:4000])
            db.set_project_status(project_id, "failed")
        except Exception:
            log.exception("render.fail_record_failed", project_id=project_id, job_id=job_id)
        raise
