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
from app.db.models import Project

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

    response.status_code = status.HTTP_202_ACCEPTED
    task_id = send_celery(
        "worker.render.language",
        str(project_id), body.language, idempotency_key,
    )
    return {"job_id": task_id, "language": body.language}


async def _project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project
