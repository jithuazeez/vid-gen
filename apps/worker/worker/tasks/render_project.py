"""Phase B controller: full render of the primary language.

Architecture.md §8 DAG. Per scene: voice → (gated)lipsync → subtitles → composite.
We await whisper_align before composite because composite burns in the SRT.
"""
from __future__ import annotations

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


def _record_modal_calls(job_id: str, calls: dict[str, list[str]]) -> None:
    """Persist Modal FunctionCall ids on render_jobs.modal_call_ids so a
    cancellation request can reach Modal. Architecture.md §8.

    `calls` is keyed by stage; values are lists of `object_id` strings.
    Updates merge into the existing JSONB column.
    """
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

    scenes = db.list_scenes(project_id)

    # ─── Phase B-1: visuals (LTX) + music (ACE-Step) in parallel ────────
    publish_event(project_id, "stage_change", {"stage": "scenes"})

    visual_calls = []
    for s in scenes:
        # Skip the spawn entirely if the scene_video is already cached
        # (e.g. user is re-running after a partial failure).
        if s.get("scene_video_asset_id"):
            continue
        h = manifest.scene_video_hash({**s, "seed": project.get("seed")})
        if manifest.is_cached(h):
            publish_event(project_id, "scene_ready",
                          {"scene_id": str(s["id"]), "kind": "scene_video",
                           "cache_hit": True,
                           "asset_url": signed_url_for_asset(s.get("scene_video_asset_id"))})
            continue
        visual_calls.append((s, ltx_render.spawn(project_id=project_id, scene_id=str(s["id"]))))

    music_call = None
    if project.get("music_enabled"):
        publish_event(project_id, "stage_change", {"stage": "music"})
        music_call = acestep_music.spawn(project_id=project_id)

    _record_modal_calls(job_id, {
        "ltx_render":     [c for c in (_call_id(call) for _, call in visual_calls) if c],
        "acestep_music":  [c for c in [_call_id(music_call)] if c] if music_call else [],
    })

    for scene, call in visual_calls:
        result = call.get()
        aid = result.get("asset_id") if isinstance(result, dict) else None
        publish_event(project_id, "scene_ready",
                      {"scene_id": str(scene["id"]), "kind": "scene_video",
                       "asset_id": aid, "asset_url": signed_url_for_asset(aid)})
    if music_call is not None:
        music_call.get()
    publish_event(project_id, "progress", {"percent": 40})

    # ─── Phase B-2: per-scene language pipeline ─────────────────────────
    # Per scene order:
    #   1. voice (await; needed by lipsync + whisper)
    #   2. lipsync (await; only if has_speaker)
    #   3. whisper subtitles (await; needed by composite for burn-in)
    #   4. composite (spawn; await all at the end)
    #
    # Step 1-3 are awaited per scene but the composites all run in
    # parallel, which is the right shape: voice/lipsync/whisper are
    # cheap CPU/T4 calls, composite is the expensive concat.

    publish_event(project_id, "stage_change", {"stage": "voice"})
    composite_calls = []
    for s in scenes:
        sid = str(s["id"])

        voice_call = generate_voice.spawn(project_id=project_id, scene_id=sid, language=lang)
        voice_call.get()
        publish_event(project_id, "asset_progress",
                      {"asset_type": "voice", "scene_id": sid, "percent": 100})

        if s.get("has_speaker"):
            ls = musetalk_sync.spawn(project_id=project_id, scene_id=sid,
                                      language=lang, has_speaker=True)
            ls.get()
            publish_event(project_id, "asset_progress",
                          {"asset_type": "lipsync_video", "scene_id": sid, "percent": 100})

        # Subtitles MUST finish before composite (composite burns the SRT in).
        sub_call = whisper_align.spawn(project_id=project_id, scene_id=sid, language=lang)
        sub_call.get()
        publish_event(project_id, "asset_progress",
                      {"asset_type": "subtitle_srt", "scene_id": sid, "percent": 100})

        composite_calls.append((sid, ffmpeg_composite.spawn(
            project_id=project_id, scene_id=sid, language=lang,
        )))

    _record_modal_calls(job_id, {
        "ffmpeg_composite": [c for c in (_call_id(call) for _, call in composite_calls) if c],
    })

    for sid, call in composite_calls:
        result = call.get()
        aid = result.get("asset_id") if isinstance(result, dict) else None
        publish_event(project_id, "scene_ready",
                      {"scene_id": sid, "kind": "composite",
                       "asset_id": aid, "asset_url": signed_url_for_asset(aid)})
    publish_event(project_id, "progress", {"percent": 90})

    # ─── Phase B-3: final export ───────────────────────────────────────
    publish_event(project_id, "stage_change", {"stage": "export"})
    export_result = final_export.remote(
        project_id=project_id, language=lang,
        quality="1080p", subtitles_mode="burned",
    )
    export_asset_id = export_result.get("asset_id") if isinstance(export_result, dict) else None
    db.update_job(
        job_id, status="succeeded", current_stage="done",
        progress={"percent": 100, "final_export_asset_id": export_asset_id},
    )
    db.set_project_status(project_id, "ready")
    db.append_available_language(project_id, lang)
    publish_event(project_id, "done", {"language": lang, "export": export_result,
                                       "final_export_asset_id": export_asset_id})
    return job_id
