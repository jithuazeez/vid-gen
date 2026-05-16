"""PATCH /projects/:id/audio — music volume slider on Screen 4.

Stored as `brief.audio.music_volume_db` so re-render can pick it up.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import Project

router = APIRouter(prefix="/projects", tags=["audio"])


class AudioPatch(BaseModel):
    music_volume_db: float = Field(ge=-60.0, le=6.0)


@router.patch("/{project_id}/audio")
async def patch_audio(
    project_id: uuid.UUID,
    body: AudioPatch,
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    brief = dict(project.brief or {})
    audio = dict(brief.get("audio") or {})
    audio["music_volume_db"] = float(body.music_volume_db)
    brief["audio"] = audio
    project.brief = brief
    await session.commit()
    return {"ok": True, "music_volume_db": body.music_volume_db}
