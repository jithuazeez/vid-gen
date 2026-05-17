"""Project CRUD — POST /projects, GET /projects/:id, PATCH /projects/:id.

Architecture.md §7.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Asset, Project, RenderJob, Scene, Subtitle
from app.schemas import (
    AssetState,
    JobOut,
    ProjectCreate,
    ProjectOut,
    ProjectPatch,
    SubtitleOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/ping", status_code=status.HTTP_202_ACCEPTED)
async def ping(project_id: uuid.UUID) -> dict:
    """Day-1 smoke: enqueue a Celery task that calls Modal `ping` and SSEs back."""
    task_id = send_celery("worker.ping", str(project_id))
    return {"job_id": task_id}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    project = Project(title=body.title, status="draft", brief={})
    session.add(project)
    await session.commit()
    project = await _load_project(session, project.id)
    return _to_out(project, latest_job=None, subtitles=[])


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    project = await _load_project(session, project_id)
    latest_job = await _latest_job(session, project_id)
    subs = await _project_subtitles(session, project_id)
    return _to_out(project, latest_job, subs)


@router.patch("/{project_id}", response_model=ProjectOut)
async def patch_project(
    project_id: uuid.UUID,
    body: ProjectPatch,
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    project = await _load_project(session, project_id)

    updates = body.model_dump(exclude_unset=True)
    if "brief" in updates and updates["brief"] is not None:
        # Stored as JSONB; merge so partial PATCHes don't wipe slots.
        merged = {**(project.brief or {}), **updates.pop("brief")}
        project.brief = merged
        # Hydrate denormalized columns from the brief.
        if "primary_language" in merged:
            project.primary_language = merged["primary_language"]
            if not project.active_language:
                project.active_language = merged["primary_language"]
        if "aspect_ratio" in merged:
            project.aspect_ratio = merged["aspect_ratio"]
        if "duration_seconds" in merged:
            project.duration_seconds = merged["duration_seconds"]
        if "has_characters" in merged:
            project.has_characters = bool(merged["has_characters"])
        if "music_enabled" in merged:
            project.music_enabled = bool(merged["music_enabled"])

    for k, v in updates.items():
        setattr(project, k, v)

    await session.commit()
    await session.refresh(project)
    project = await _load_project(session, project_id)
    latest_job = await _latest_job(session, project_id)
    subs = await _project_subtitles(session, project_id)
    return _to_out(project, latest_job, subs)


async def _load_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await session.execute(
        select(Project)
        .options(
            selectinload(Project.scenes),
            selectinload(Project.overlays),
            selectinload(Project.assets),
        )
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


async def _project_subtitles(
    session: AsyncSession, project_id: uuid.UUID
) -> list[Subtitle]:
    res = await session.execute(
        select(Subtitle)
        .join(Scene, Subtitle.scene_id == Scene.id)
        .where(Scene.project_id == project_id)
    )
    return list(res.scalars().all())


async def _latest_job(session: AsyncSession, project_id: uuid.UUID) -> RenderJob | None:
    result = await session.execute(
        select(RenderJob)
        .where(RenderJob.project_id == project_id)
        .order_by(RenderJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _to_out(
    project: Project,
    latest_job: RenderJob | None,
    subtitles: list[Subtitle] | None = None,
) -> ProjectOut:
    # Filter assets down to "interesting" ones — the editor needs scene-scoped
    # rows (one per (scene, asset_type) slot). Thumbnails and character refs
    # are stored as scene-less or always-ready and the timeline doesn't
    # render them.
    timeline_assets = [
        a for a in (project.assets or [])
        if a.asset_type in {"scene_video", "voice", "lipsync_video",
                            "subtitle_srt", "composite"}
    ]
    return ProjectOut.model_validate(
        {
            **{k: getattr(project, k) for k in ProjectOut.model_fields if hasattr(project, k)},
            "scenes": list(project.scenes),
            "overlays": list(project.overlays),
            "subtitles": [SubtitleOut.model_validate(s) for s in (subtitles or [])],
            "assets": [AssetState.model_validate(a) for a in timeline_assets],
            "latest_job": JobOut.model_validate(latest_job) if latest_job else None,
        }
    )
