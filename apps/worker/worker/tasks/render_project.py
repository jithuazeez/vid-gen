"""Phase B controller: full render of the primary language.

Rewrite of the previous stage-barrier orchestrator into a per-asset
fan-out. Concretely:

- All ``ltx_render`` and ``generate_voice`` calls are spawned in parallel
  the moment the task starts — voice does **not** wait for video, and
  scene N+1's video does not wait for scene N's video.
- ``mediapipe_face`` chains off ``ltx_render`` per scene.
- ``whisper_align`` chains off ``generate_voice`` per scene.
- ``musetalk_sync`` fires the moment both LTX and voice are ready for a
  speaker scene.
- ``ffmpeg_composite`` fires per scene as soon as that scene's full set
  of prerequisites is ready.
- ``final_export`` runs once after every composite has landed.

Modal ``FunctionCall.get()`` is blocking; we drive concurrency with a
``ThreadPoolExecutor`` and ``as_completed`` so independent branches make
progress simultaneously. Each transition emits SSE so the editor
timeline fills tile by tile.
"""
from __future__ import annotations

import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

import structlog
from sqlalchemy import text

from worker import db
from worker.asset_urls import signed_url_for_asset
from worker.celery_app import celery_app
from worker.modal_client import (
    ffmpeg_composite,
    final_export,
    generate_voice,
    ltx_render,
    mediapipe_face,
    musetalk_sync,
    whisper_align,
)
from worker.sse import publish_event

log = structlog.get_logger(__name__)


def _record_modal_calls(job_id: str, calls: dict[str, list[str]]) -> None:
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


def _emit_asset(project_id: str, kind: str, scene_id: str | None,
                asset_type: str, language: str | None = None,
                **extra) -> None:
    """Publish an asset-lifecycle event. Kind: started | ready | failed."""
    payload = {
        "scene_id": scene_id,
        "asset_type": asset_type,
        "language": language,
        **extra,
    }
    publish_event(project_id, f"asset.{kind}", payload)


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
    by_id = {str(s["id"]): s for s in scenes}
    log.info("render.scenes_loaded", project_id=project_id, job_id=job_id,
             scene_count=len(scenes))

    # Per-scene readiness flags drive the dynamic "what can fire next" logic.
    ltx_ready: dict[str, bool] = {}
    voice_ready: dict[str, bool] = {}
    whisper_ready: dict[str, bool] = {}
    mediapipe_ready: dict[str, bool] = {}
    musetalk_ready: dict[str, bool] = {}
    composite_ready: dict[str, bool] = {}
    musetalk_started: dict[str, bool] = {}
    composite_started: dict[str, bool] = {}

    def _has_voice_branch(s: dict) -> bool:
        return bool(s.get("has_speaker")) and bool(
            (s.get("narration_script") or "").strip()
        )

    def _scene_composite_inputs_ready(sid: str) -> bool:
        s = by_id[sid]
        if sid not in ltx_ready:
            return False
        if _has_voice_branch(s):
            if sid not in voice_ready or sid not in whisper_ready:
                return False
            if sid not in musetalk_ready:
                return False
        return True

    # Thread pool drives concurrent .get() calls on Modal FunctionCalls.
    # Modal call I/O is the bottleneck; threads are cheap.
    pool_size = max(8, len(scenes) * 4)
    executor = ThreadPoolExecutor(max_workers=pool_size,
                                  thread_name_prefix="render")
    # Maps the in-flight Future back to (kind, scene_id) so the main loop
    # knows which branch a completion belongs to.
    pending: dict[Future, tuple[str, str]] = {}

    def _await(call, kind: str, sid: str) -> None:
        fut = executor.submit(call.get)
        pending[fut] = (kind, sid)

    try:
        publish_event(project_id, "stage_change", {"stage": "render"})
        db.update_job(job_id, current_stage="render")

        # ─── Fan out scene_video + voice in parallel for every scene ────
        ltx_call_ids: list[str] = []
        voice_call_ids: list[str] = []

        for s in scenes:
            sid = str(s["id"])

            if s.get("scene_video_asset_id"):
                # Cached from a previous run — mark ready immediately.
                ltx_ready[sid] = True
                _emit_asset(project_id, "ready", sid, "scene_video",
                            asset_id=s.get("scene_video_asset_id"),
                            asset_url=signed_url_for_asset(s.get("scene_video_asset_id")),
                            cache_hit=True)
                db.set_asset_status(project_id=project_id, scene_id=sid,
                                    asset_type="scene_video", language=None,
                                    status="ready")
            else:
                call = ltx_render.spawn(project_id=project_id, scene_id=sid)
                cid = _call_id(call)
                if cid:
                    ltx_call_ids.append(cid)
                _emit_asset(project_id, "started", sid, "scene_video",
                            modal_call_id=cid)
                db.set_asset_status(project_id=project_id, scene_id=sid,
                                    asset_type="scene_video", language=None,
                                    status="generating", progress=10)
                _await(call, "ltx", sid)

            if _has_voice_branch(s):
                vc = generate_voice.spawn(project_id=project_id, scene_id=sid,
                                          language=lang)
                cid = _call_id(vc)
                if cid:
                    voice_call_ids.append(cid)
                _emit_asset(project_id, "started", sid, "voice",
                            language=lang, modal_call_id=cid)
                db.set_asset_status(project_id=project_id, scene_id=sid,
                                    asset_type="voice", language=lang,
                                    status="generating", progress=10)
                _await(vc, "voice", sid)

        _record_modal_calls(job_id, {
            "ltx_render": ltx_call_ids,
            "generate_voice": voice_call_ids,
        })

        # If a scene has no LTX call and no voice call (fully cached and
        # non-speaker), still need composite to fire. Seed mediapipe.
        for s in scenes:
            sid = str(s["id"])
            if sid in ltx_ready:
                mp = mediapipe_face.spawn(project_id=project_id, scene_id=sid)
                _await(mp, "mediapipe", sid)

        # ─── Drain completions and spawn dependents on the fly ──────────
        while pending:
            done = next(as_completed(pending.keys()))
            kind, sid = pending.pop(done)
            try:
                result = done.result()
            except Exception as e:
                _handle_failure(e, kind, sid, project_id, job_id, lang)
                raise
            _on_complete(kind, sid, result, project_id, job_id, lang,
                         by_id, ltx_ready, voice_ready, whisper_ready,
                         mediapipe_ready, musetalk_ready, composite_ready,
                         musetalk_started, composite_started, _await)

            # After every completion, check if any scene's composite can fire.
            for s in scenes:
                cid = str(s["id"])
                if cid in composite_started or cid in composite_ready:
                    continue
                if not _scene_composite_inputs_ready(cid):
                    continue
                composite_started[cid] = True
                cc = ffmpeg_composite.spawn(project_id=project_id,
                                            scene_id=cid, language=lang)
                _emit_asset(project_id, "started", cid, "composite",
                            language=lang, modal_call_id=_call_id(cc))
                db.set_asset_status(project_id=project_id, scene_id=cid,
                                    asset_type="composite", language=lang,
                                    status="generating", progress=10)
                _await(cc, "composite", cid)

            # Overall % progress for the legacy `progress` event.
            total = max(1, len(scenes))
            done_n = sum(1 for s in scenes if str(s["id"]) in composite_ready)
            pct = min(95, int((done_n / total) * 90))
            publish_event(project_id, "progress", {"percent": pct})

        # ─── Final export once every per-scene composite is ready ───────
        publish_event(project_id, "stage_change", {"stage": "export"})
        db.update_job(job_id, current_stage="export")
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
                 final_export_asset_id=export_asset_id,
                 final_export_duration_s=round(time.monotonic() - t0, 2))
        return job_id

    except Exception:
        log.exception("render.unhandled", project_id=project_id, job_id=job_id)
        try:
            db.update_job(job_id, status="failed",
                          error=traceback.format_exc()[:4000])
            db.set_project_status(project_id, "failed")
        except Exception:
            log.exception("render.fail_record_failed",
                          project_id=project_id, job_id=job_id)
        raise
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _on_complete(kind, sid, result, project_id, job_id, lang, by_id,
                 ltx_ready, voice_ready, whisper_ready, mediapipe_ready,
                 musetalk_ready, composite_ready, musetalk_started,
                 composite_started, _await):
    """React to a single Modal call finishing. Spawns the next per-scene
    step inline when its dependencies are ready."""
    s = by_id[sid]
    aid = result.get("asset_id") if isinstance(result, dict) else None

    if kind == "ltx":
        ltx_ready[sid] = True
        _emit_asset(project_id, "ready", sid, "scene_video",
                    asset_id=aid,
                    asset_url=signed_url_for_asset(aid) if aid else None)
        db.set_asset_status(project_id=project_id, scene_id=sid,
                            asset_type="scene_video", language=None,
                            status="ready")
        # Per-scene face detection is cheap and best-effort.
        mp = mediapipe_face.spawn(project_id=project_id, scene_id=sid)
        _await(mp, "mediapipe", sid)

        # If voice already done and scene is a speaker, kick musetalk.
        if (s.get("has_speaker")
                and sid in voice_ready
                and sid not in musetalk_started):
            musetalk_started[sid] = True
            ms = musetalk_sync.spawn(project_id=project_id, scene_id=sid,
                                     language=lang, has_speaker=True)
            _emit_asset(project_id, "started", sid, "lipsync_video",
                        language=lang, modal_call_id=_call_id(ms))
            db.set_asset_status(project_id=project_id, scene_id=sid,
                                asset_type="lipsync_video", language=lang,
                                status="generating", progress=10)
            _await(ms, "musetalk", sid)

    elif kind == "voice":
        voice_ready[sid] = True
        _emit_asset(project_id, "ready", sid, "voice", language=lang,
                    asset_id=aid)
        db.set_asset_status(project_id=project_id, scene_id=sid,
                            asset_type="voice", language=lang,
                            status="ready")
        # Spawn whisper_align — depends only on audio.
        wa = whisper_align.spawn(project_id=project_id, scene_id=sid,
                                 language=lang)
        _emit_asset(project_id, "started", sid, "subtitle_srt",
                    language=lang, modal_call_id=_call_id(wa))
        db.set_asset_status(project_id=project_id, scene_id=sid,
                            asset_type="subtitle_srt", language=lang,
                            status="generating", progress=10)
        _await(wa, "whisper", sid)

        if (s.get("has_speaker")
                and sid in ltx_ready
                and sid not in musetalk_started):
            musetalk_started[sid] = True
            ms = musetalk_sync.spawn(project_id=project_id, scene_id=sid,
                                     language=lang, has_speaker=True)
            _emit_asset(project_id, "started", sid, "lipsync_video",
                        language=lang, modal_call_id=_call_id(ms))
            db.set_asset_status(project_id=project_id, scene_id=sid,
                                asset_type="lipsync_video", language=lang,
                                status="generating", progress=10)
            _await(ms, "musetalk", sid)

    elif kind == "whisper":
        whisper_ready[sid] = True
        _emit_asset(project_id, "ready", sid, "subtitle_srt",
                    language=lang, asset_id=aid)
        db.set_asset_status(project_id=project_id, scene_id=sid,
                            asset_type="subtitle_srt", language=lang,
                            status="ready")
        # Tell the editor to swap estimated cues for refined ones.
        publish_event(project_id, "subtitle.refined",
                      {"scene_id": sid, "language": lang})

    elif kind == "mediapipe":
        mediapipe_ready[sid] = True
        # Best-effort; no UI tile, no SSE.

    elif kind == "musetalk":
        musetalk_ready[sid] = True
        _emit_asset(project_id, "ready", sid, "lipsync_video",
                    language=lang, asset_id=aid)
        db.set_asset_status(project_id=project_id, scene_id=sid,
                            asset_type="lipsync_video", language=lang,
                            status="ready")

    elif kind == "composite":
        composite_ready[sid] = True
        _emit_asset(project_id, "ready", sid, "composite",
                    language=lang, asset_id=aid,
                    asset_url=signed_url_for_asset(aid) if aid else None)
        db.set_asset_status(project_id=project_id, scene_id=sid,
                            asset_type="composite", language=lang,
                            status="ready")
        # Legacy event the existing review code still listens for.
        publish_event(project_id, "scene_ready",
                      {"scene_id": sid, "kind": "composite",
                       "asset_id": aid,
                       "asset_url": signed_url_for_asset(aid) if aid else None})


def _handle_failure(exc, kind, sid, project_id, job_id, lang):
    log.error("modal.await.failed",
              kind=kind, scene_id=sid, project_id=project_id, job_id=job_id,
              error=str(exc), error_type=type(exc).__name__,
              traceback=traceback.format_exc())
    asset_type = {
        "ltx": "scene_video", "voice": "voice", "whisper": "subtitle_srt",
        "mediapipe": "face_data", "musetalk": "lipsync_video",
        "composite": "composite",
    }.get(kind, kind)
    try:
        db.set_asset_status(
            project_id=project_id, scene_id=sid, asset_type=asset_type,
            language=lang if kind != "ltx" else None,
            status="failed",
        )
        db.update_job(job_id, status="failed", current_stage=kind,
                      error=f"{kind} failed (scene {sid}): "
                            f"{type(exc).__name__}: {exc}"[:4000])
        db.set_project_status(project_id, "failed")
    except Exception:
        log.exception("render.fail_record_failed",
                      project_id=project_id, job_id=job_id)
    _emit_asset(project_id, "failed", sid, asset_type,
                language=lang, error=str(exc), error_type=type(exc).__name__)
    publish_event(project_id, "error", {
        "stage": kind, "scene_id": sid,
        "error_type": type(exc).__name__, "message": str(exc),
    })
