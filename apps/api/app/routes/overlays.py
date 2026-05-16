"""Overlay CRUD — POST/PATCH/DELETE /overlays."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import Overlay
from app.schemas import OverlayOut

router = APIRouter(prefix="/overlays", tags=["overlays"])


class OverlayCreate(BaseModel):
    project_id: uuid.UUID
    overlay_type: str = "cta"
    text: str | None = None
    start_seconds: float
    end_seconds: float
    position: dict = {}
    animation: str = "fade"
    style: dict = {}


class OverlayPatch(BaseModel):
    overlay_type: str | None = None
    text: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    position: dict | None = None
    animation: str | None = None
    style: dict | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_overlay(
    body: OverlayCreate,
    session: AsyncSession = Depends(get_session),
) -> OverlayOut:
    overlay = Overlay(
        project_id=body.project_id,
        overlay_type=body.overlay_type,
        text=body.text,
        start_seconds=Decimal(str(body.start_seconds)),
        end_seconds=Decimal(str(body.end_seconds)),
        position=body.position,
        animation=body.animation,
        style=body.style,
    )
    session.add(overlay)
    await session.commit()
    await session.refresh(overlay)
    return OverlayOut.model_validate(overlay)


@router.patch("/{overlay_id}")
async def patch_overlay(
    overlay_id: uuid.UUID,
    body: OverlayPatch,
    session: AsyncSession = Depends(get_session),
) -> OverlayOut:
    overlay = await _overlay_or_404(session, overlay_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k in ("start_seconds", "end_seconds") and v is not None:
            setattr(overlay, k, Decimal(str(v)))
        else:
            setattr(overlay, k, v)
    await session.commit()
    await session.refresh(overlay)
    return OverlayOut.model_validate(overlay)


@router.delete("/{overlay_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_overlay(
    overlay_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    overlay = await _overlay_or_404(session, overlay_id)
    await session.delete(overlay)
    await session.commit()


async def _overlay_or_404(session: AsyncSession, overlay_id: uuid.UUID) -> Overlay:
    res = await session.execute(select(Overlay).where(Overlay.id == overlay_id))
    overlay = res.scalar_one_or_none()
    if overlay is None:
        raise HTTPException(status_code=404, detail="overlay not found")
    return overlay
