"""Phase A: turn a finalised brief into a scene plan + SDXL thumbnails +
character reference images.

DAG (Phase A):
  scene_engine_plan ── via API /internal/scene-plan
       ├── thumbnails (sdxl_thumbnail) per scene  — awaited
       └── character_refs (sdxl_character_ref) per character — awaited
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx
from sqlalchemy import text

from worker import db
from worker.asset_urls import signed_url_for_asset
from worker.celery_app import celery_app
from worker.modal_client import sdxl_character_ref, sdxl_thumbnail
from worker.sse import publish_event

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")


@celery_app.task(name="worker.storyboard.generate", bind=True, max_retries=2)
def generate_storyboard(self, project_id: str, idempotency_key: str | None = None,
                        job_id: str | None = None) -> str:
    if job_id:
        db.start_job(job_id)
    else:
        job_id = db.create_job(
            project_id=project_id,
            job_type="storyboard",
            idempotency_key=idempotency_key or self.request.id,
        )
    db.set_project_status(project_id, "planning")
    publish_event(project_id, "stage_change", {"stage": "scene_plan", "job_id": job_id})

    project = db.fetch_project(project_id)
    if project is None:
        db.update_job(job_id, status="failed", error="project not found")
        publish_event(project_id, "error", {"message": "project not found"})
        return job_id

    plan = _plan(project)
    db.upsert_scenes(project_id, plan.get("scenes", []))
    # Surface placeholder subtitle cues on the editor timeline as soon as
    # the plan exists — whisper_align overwrites these per-scene with
    # word-accurate timings once each scene's audio is ready.
    sb_lang = project.get("primary_language") or "en"
    try:
        db.seed_estimated_subtitle_cues(project_id, sb_lang)
    except Exception as exc:
        publish_event(project_id, "warning",
                      {"stage": "estimated_cues", "message": str(exc)})
    characters = _upsert_characters(project_id, plan.get("characters", []))

    publish_event(project_id, "stage_change",
                  {"stage": "thumbnails", "scenes": len(plan.get("scenes", []))})

    # ─── Phase A fan-out: thumbnails + character refs in parallel ─────
    thumb_calls = []
    for sc in db.list_scenes(project_id):
        thumb_calls.append((sc, sdxl_thumbnail.spawn(
            project_id=project_id,
            scene_id=str(sc["id"]),
            prompt=sc["visual_prompt"],
        )))

    # Explainer mode forces a frontal, locked-off bust shot so the
    # downstream LipSync face detector can lock on every frame. The SDXL
    # reference image is the first frame LTX animates from, so it has to
    # match — flip the character_ref into frontal mode when the brief
    # asks for explainer.
    brief = project.get("brief") or {}
    frontal = (brief.get("video_type") == "explainer")

    char_calls = []
    for ch in characters:
        char_calls.append((ch, sdxl_character_ref.spawn(
            project_id=project_id,
            character_id=str(ch["id"]),
            name=ch["name"],
            description=ch["description"],
            frontal=frontal,
        )))

    # Await both groups concurrently so each thumbnail's `scene_ready`
    # event fires the instant *that* thumb finishes — not in spawn order.
    # Without the pool, the for-loop blocks on call #1's `.get()`, and any
    # thumbs that finished earlier sit in a queue: the UI then sees the
    # whole batch arrive in one burst. Modal call I/O is the bottleneck so
    # threads are cheap. Same pattern as render_project.py.
    pool_size = max(4, len(thumb_calls) + len(char_calls))
    with ThreadPoolExecutor(max_workers=pool_size,
                            thread_name_prefix="storyboard") as executor:
        futs: dict = {}
        for sc, call in thumb_calls:
            futs[executor.submit(call.get)] = ("thumb", sc)
        for ch, call in char_calls:
            futs[executor.submit(call.get)] = ("char", ch)

        for fut in as_completed(futs):
            kind, obj = futs[fut]
            try:
                result = fut.result()
            except Exception as exc:
                publish_event(project_id, "warning",
                              {"stage": kind, "message": str(exc)})
                continue
            aid = result.get("asset_id") if isinstance(result, dict) else None
            if kind == "thumb":
                if aid:
                    _set_scene_thumbnail(str(obj["id"]), aid)
                publish_event(project_id, "scene_ready",
                              {"scene_id": str(obj["id"]), "kind": "thumbnail",
                               "asset_id": aid,
                               "asset_url": signed_url_for_asset(aid)})
            else:
                if aid:
                    _set_character_ref(str(obj["id"]), aid)
                publish_event(project_id, "asset_progress",
                              {"asset_type": "character_ref",
                               "character_id": str(obj["id"]),
                               "asset_id": aid})

    db.update_job(job_id, status="succeeded", current_stage="done")
    publish_event(project_id, "done", {"job_id": job_id, "phase": "storyboard"})
    return job_id


# ── DB helpers (kept here so worker doesn't need API ORM models) ───────


def _plan(project: dict[str, Any]) -> dict[str, Any]:
    """Try the API's scene-engine endpoint; fall back to a canned plan."""
    try:
        r = httpx.post(
            f"{API_BASE}/internal/scene-plan",
            json={"project_id": str(project["id"])},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"scenes": _fallback_scenes(project), "characters": _fallback_chars(project)}


def _fallback_scenes(project: dict[str, Any]) -> list[dict[str, Any]]:
    brief = project.get("brief") or {}
    topic = brief.get("topic") or project.get("title") or "your story"
    duration = int(project.get("duration_seconds") or 30)
    n = max(3, min(6, duration // 6))
    per = round(duration / n, 2)
    canned = [
        ("Opening shot", "Wide cinematic establishing shot, soft morning light."),
        ("Detail close-up", "Macro shot, shallow depth of field, gentle motion."),
        ("Action beat", "Medium shot, character or object in motion, golden hour."),
        ("Atmosphere", "B-roll, texture and mood, warm tone."),
        ("Brand reveal", "Logo lock-up over textured background, slow zoom."),
        ("Closing", "Final wide shot, fade-to-brand."),
    ]
    return [
        {
            "scene_index": i + 1, "duration_seconds": per,
            "visual_prompt": f"{prompt} Subject: {topic}.",
            "narration_script": f"{title}: a moment of {topic}.",
            "has_speaker": False, "subtitle_position": "auto",
        }
        for i, (title, prompt) in enumerate(canned[:n])
    ]


def _fallback_chars(project: dict[str, Any]) -> list[dict[str, Any]]:
    if not project.get("has_characters"):
        return []
    return [{
        "name": "Presenter",
        "description": "Friendly mid-20s presenter, neutral background, warm smile, "
                       "natural lighting, eye contact with the camera.",
    }]


def _upsert_characters(project_id: str, plan_chars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with db.session_scope() as s:
        # Clear stale characters for a clean re-plan.
        s.execute(text("DELETE FROM characters WHERE project_id = :pid"),
                  {"pid": project_id})
        for ch in plan_chars:
            cid = uuid.uuid4()
            s.execute(
                text("INSERT INTO characters (id, project_id, name, description) "
                     "VALUES (:id, :pid, :name, :desc)"),
                {"id": cid, "pid": project_id,
                 "name": ch["name"], "desc": ch["description"]},
            )
            out.append({"id": cid, "name": ch["name"], "description": ch["description"]})
    return out


def _set_scene_thumbnail(scene_id: str, asset_id: str) -> None:
    with db.session_scope() as s:
        s.execute(
            text("UPDATE scenes SET thumbnail_asset_id = :aid WHERE id = :sid"),
            {"aid": asset_id, "sid": scene_id},
        )


def _set_character_ref(character_id: str, asset_id: str) -> None:
    with db.session_scope() as s:
        s.execute(
            text("UPDATE characters SET reference_image_asset_id = :aid WHERE id = :cid"),
            {"aid": asset_id, "cid": character_id},
        )
