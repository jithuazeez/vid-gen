"""POST /projects/:id/generate — kick off the full Phase B render pipeline.

Architecture.md §7. Split out from `language.py` so each route file maps to
one concept (this one owns the initial render; language.py owns
re-renders for additional languages).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Asset, Project, RenderJob, Scene

router = APIRouter(prefix="/projects", tags=["render"])


@router.post("/{project_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def kickoff_render(
    project_id: uuid.UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # If an idempotency key was supplied and a job already exists for it,
    # return that job so the client can re-subscribe without triggering a
    # duplicate render.
    if idempotency_key:
        existing = await session.execute(
            select(RenderJob).where(RenderJob.idempotency_key == idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return {"job_id": str(existing_job.id)}

    lang = project.primary_language or "en"
    project.status = "rendering"

    # Create the job row before enqueueing so /jobs/{id}/events returns 200
    # the moment the client tries to subscribe (no race with the worker).
    job = RenderJob(
        project_id=project_id,
        job_type="initial_render",
        language=lang,
        status="pending",
        current_stage="queued",
        idempotency_key=idempotency_key,
    )
    session.add(job)
    await session.flush()

    # Seed per-asset slot rows so the editor timeline renders the right
    # number of queued tiles immediately on first load — no waiting for
    # SSE events to populate the slots.
    await _seed_asset_slots(session, project_id, lang)

    await session.commit()

    send_celery(
        "worker.render.project",
        str(project_id), lang, idempotency_key,
        job_id=str(job.id),
    )
    return {"job_id": str(job.id)}


async def _seed_asset_slots(
    session: AsyncSession, project_id: uuid.UUID, language: str
) -> None:
    """Idempotently insert (scene, asset_type) slot rows for every per-scene
    artifact the editor renders. Slot rows carry status='queued' and no
    storage_key; worker tasks fill them in as artifacts land.

    Voice/lipsync/subtitle slots are seeded only for scenes whose
    has_speaker flag is set — those are the only scenes that produce them.
    """
    res = await session.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
    )
    scenes = list(res.scalars().all())

    # Pull existing slots so re-kicking generate doesn't duplicate rows.
    existing_res = await session.execute(
        select(Asset.scene_id, Asset.asset_type, Asset.language)
        .where(Asset.project_id == project_id, Asset.status != "ready")
    )
    existing = {(str(r[0]) if r[0] else None, r[1], r[2] or "") for r in existing_res.all()}

    def _maybe_add(scene: Scene, asset_type: str, lang: str | None) -> None:
        key = (str(scene.id), asset_type, lang or "")
        if key in existing:
            return
        # Sentinel content_hash for slot rows — replaced when the artifact
        # actually lands. Empty string would collide on the unique index;
        # use a unique-per-slot synthetic value.
        sentinel = f"slot:{scene.id}:{asset_type}:{lang or ''}"
        session.add(
            Asset(
                project_id=project_id,
                scene_id=scene.id,
                asset_type=asset_type,
                language=lang,
                storage_key="",
                content_hash=sentinel,
                status="queued",
                progress=0,
            )
        )
        existing.add(key)

    for scene in scenes:
        _maybe_add(scene, "scene_video", None)
        _maybe_add(scene, "composite", language)
        if scene.has_speaker:
            _maybe_add(scene, "voice", language)
            _maybe_add(scene, "subtitle_srt", language)
            _maybe_add(scene, "lipsync_video", language)
