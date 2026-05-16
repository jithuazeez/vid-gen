"""POST /projects/:id/export — final encode."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Project, RenderJob

router = APIRouter(prefix="/projects", tags=["export"])


class ExportBody(BaseModel):
    language: str
    quality: str = "1080p"
    subtitles: str = "burned"


@router.post("/{project_id}/export", status_code=status.HTTP_202_ACCEPTED)
async def kickoff_export(
    project_id: uuid.UUID,
    body: ExportBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    if idempotency_key:
        existing = await session.execute(
            select(RenderJob).where(RenderJob.idempotency_key == idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return {"job_id": str(existing_job.id)}

    # Create the RenderJob row up front so /jobs/{id}/events resolves
    # immediately. Otherwise the UI subscribes to the Celery task id, which
    # doesn't exist in render_jobs, and gets 404.
    job = RenderJob(
        project_id=project_id,
        job_type="export",
        language=body.language,
        status="pending",
        current_stage="queued",
        idempotency_key=idempotency_key,
    )
    session.add(job)
    await session.commit()

    send_celery(
        "worker.export.run",
        str(project_id), body.language, body.quality, body.subtitles, idempotency_key,
        job_id=str(job.id),
    )
    return {"job_id": str(job.id)}
