"""PATCH /subtitles/:id — edit cues / position for a single scene+language pair.

Architecture.md §7. Used by the SubtitleEditor on Screen 4.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import Subtitle
from app.schemas import SubtitleCue, SubtitleOut

router = APIRouter(prefix="/subtitles", tags=["subtitles"])


class SubtitlePatch(BaseModel):
    cues: list[SubtitleCue] | None = None
    generated_position: str | None = None


@router.patch("/{subtitle_id}", response_model=SubtitleOut)
async def patch_subtitle(
    subtitle_id: uuid.UUID,
    body: SubtitlePatch,
    session: AsyncSession = Depends(get_session),
) -> SubtitleOut:
    sub = await _get_or_404(session, subtitle_id)

    updates: dict[str, Any] = body.model_dump(exclude_unset=True)
    if "cues" in updates and updates["cues"] is not None:
        # Cues are stored as JSONB list-of-dicts.
        sub.cues = [c if isinstance(c, dict) else c.model_dump() for c in updates["cues"]]
    if "generated_position" in updates:
        sub.generated_position = updates["generated_position"]

    await session.commit()
    await session.refresh(sub)
    return SubtitleOut.model_validate(sub)


@router.get("/scene/{scene_id}/{language}", response_model=SubtitleOut)
async def get_subtitle_for_scene(
    scene_id: uuid.UUID,
    language: str,
    session: AsyncSession = Depends(get_session),
) -> SubtitleOut:
    res = await session.execute(
        select(Subtitle).where(
            Subtitle.scene_id == scene_id,
            Subtitle.language == language,
        )
    )
    sub = res.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="subtitle not found")
    return SubtitleOut.model_validate(sub)


async def _get_or_404(session: AsyncSession, subtitle_id: uuid.UUID) -> Subtitle:
    res = await session.execute(select(Subtitle).where(Subtitle.id == subtitle_id))
    sub = res.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="subtitle not found")
    return sub
