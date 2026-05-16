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
from app.db.models import Project, RenderJob

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
    await session.commit()

    send_celery(
        "worker.render.project",
        str(project_id), lang, idempotency_key,
        job_id=str(job.id),
    )
    return {"job_id": str(job.id)}
