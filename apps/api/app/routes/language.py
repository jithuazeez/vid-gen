"""POST /projects/:id/regenerate-language — language switch.

The /generate endpoint lives in `render.py` (architecture.md §5).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Project, RenderJob

router = APIRouter(prefix="/projects", tags=["language"])


class LanguageBody(BaseModel):
    language: str


@router.post("/{project_id}/regenerate-language")
async def regenerate_language(
    project_id: uuid.UUID,
    body: LanguageBody,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    project = await _project_or_404(session, project_id)

    # Cache hit — instant switch, no Celery work. §7: return 200 in this case.
    if body.language in (project.available_languages or []):
        project.active_language = body.language
        await session.commit()
        response.status_code = status.HTTP_200_OK
        return {"status": "instant", "active_language": body.language}

    # Idempotent re-click: surface the existing job instead of double-enqueueing.
    if idempotency_key:
        existing = await session.execute(
            select(RenderJob).where(RenderJob.idempotency_key == idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            response.status_code = status.HTTP_202_ACCEPTED
            return {"job_id": str(existing_job.id), "language": body.language}

    # Pre-create the RenderJob row so the frontend's GET /jobs/:id/events
    # resolves to 200 immediately — same pattern as routes/render.py.
    # Without this, the route was returning the Celery task id, which has
    # no render_jobs row, and the SSE call 404'd — surfacing in the editor
    # as "pipeline failed: unknown".
    job = RenderJob(
        project_id=project_id,
        job_type="language_render",
        language=body.language,
        status="pending",
        current_stage="queued",
        idempotency_key=idempotency_key,
    )
    session.add(job)
    await session.flush()
    job_id = str(job.id)
    await session.commit()

    response.status_code = status.HTTP_202_ACCEPTED
    send_celery(
        "worker.render.language",
        str(project_id), body.language, idempotency_key,
        job_id=job_id,
    )
    return {"job_id": job_id, "language": body.language}


async def _project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project
