"""Storyboard routes — Phase A.

POST /projects/:id/storyboard/generate  → enqueue Celery `worker.storyboard.generate`
GET  /projects/:id/storyboard           → return current scene list
POST /internal/scene-plan               → called by the worker to get scenes via Gemini Pro
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Project, RenderJob, Scene
from app.orchestrators import scene_engine
from app.schemas import SceneOut

router = APIRouter(tags=["storyboard"])


@router.post("/projects/{project_id}/storyboard/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate(
    project_id: uuid.UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    project = await _project_or_404(session, project_id)

    if idempotency_key:
        existing = await session.execute(
            select(RenderJob).where(RenderJob.idempotency_key == idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return {"job_id": str(existing_job.id)}

    project.status = "planning"
    job = RenderJob(
        project_id=project_id,
        job_type="storyboard",
        status="pending",
        current_stage="queued",
        idempotency_key=idempotency_key,
    )
    session.add(job)
    await session.commit()

    send_celery("worker.storyboard.generate",
                str(project_id), idempotency_key, job_id=str(job.id))
    return {"job_id": str(job.id)}


@router.get("/projects/{project_id}/storyboard")
async def get_storyboard(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
    )
    scenes = res.scalars().all()
    return {"scenes": [SceneOut.model_validate(s).model_dump(mode="json") for s in scenes]}


class _InternalScenePlanBody(BaseModel):
    project_id: uuid.UUID


@router.post("/internal/scene-plan")
async def internal_scene_plan(
    body: _InternalScenePlanBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Internal endpoint hit by the Celery worker. Returns a Timeline."""
    project = await _project_or_404(session, body.project_id)
    references = await _collect_references(session, project.id)
    timeline = scene_engine.plan(project.brief or {}, references=references)
    return {
        "primary_language": timeline.primary_language,
        "scenes": [s.model_dump() for s in timeline.scenes],
        "characters": [c.model_dump() for c in timeline.characters],
    }


async def _collect_references(session: AsyncSession, project_id: uuid.UUID) -> dict[str, list[dict]]:
    """Fetch user-uploaded reference descriptors so the planner can use them
    as locked ground truth for the first render. Mirrors the structure used
    by scene_regen.py so the two paths stay consistent."""
    from app.db.models import Asset  # local import to avoid widening top-level deps

    res = await session.execute(
        select(Asset).where(
            Asset.project_id == project_id,
            Asset.asset_type.in_([
                "character_ref_upload", "style_ref_upload", "environment_ref_upload",
            ]),
        ).order_by(Asset.created_at.desc())
    )
    out: dict[str, list[dict]] = {"characters": [], "style": [], "environment": []}
    for asset in res.scalars().all():
        meta = asset.asset_metadata or {}
        descriptors = meta.get("descriptors") or {}
        if not isinstance(descriptors, dict) or "error" in descriptors:
            continue
        entry = {
            "asset_id":   str(asset.id),
            "name":       meta.get("character_name"),
            "descriptors": descriptors,
        }
        if asset.asset_type == "character_ref_upload":
            out["characters"].append(entry)
        elif asset.asset_type == "style_ref_upload":
            out["style"].append(entry)
        elif asset.asset_type == "environment_ref_upload":
            out["environment"].append(entry)
    return out


async def _project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project
