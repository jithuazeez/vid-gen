"""Scene CRUD — PATCH/POST/DELETE/move/regenerate."""
from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Project, Scene
from app.orchestrators import scene_regen
from app.schemas import SceneOut


def _scene_etag(scene: Scene) -> str:
    """Stable, content-derived ETag. Architecture.md §7: optimistic concurrency
    on PATCH via If-Match. Hash covers every user-editable field."""
    parts = (
        str(scene.id),
        str(scene.scene_index),
        str(scene.duration_seconds),
        scene.visual_prompt or "",
        scene.narration_script or "",
        str(bool(scene.has_speaker)),
        scene.subtitle_position or "",
        str(scene.subtitle_custom_y or ""),
    )
    return 'W/"' + hashlib.sha256("|".join(parts).encode()).hexdigest()[:16] + '"'

router = APIRouter(tags=["scenes"])


class ScenePatch(BaseModel):
    duration_seconds: float | None = None
    visual_prompt: str | None = None
    narration_script: str | None = None
    has_speaker: bool | None = None
    subtitle_position: str | None = None


class SceneCreate(BaseModel):
    project_id: uuid.UUID
    scene_index: int
    duration_seconds: float = 6.0
    visual_prompt: str = ""
    narration_script: str = ""
    has_speaker: bool = False


class SceneMoveBody(BaseModel):
    new_index: int


@router.patch("/scenes/{scene_id}")
async def patch_scene(
    scene_id: uuid.UUID,
    body: ScenePatch,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: AsyncSession = Depends(get_session),
) -> SceneOut:
    scene = await _scene_or_404(session, scene_id)

    # Optimistic concurrency: if the caller sent If-Match, only accept the
    # write when it matches the current scene's etag. Architecture.md §7.
    current = _scene_etag(scene)
    if if_match is not None and if_match != current:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"error": "etag_mismatch",
                    "current_etag": current, "supplied": if_match},
        )

    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "duration_seconds" and v is not None:
            scene.duration_seconds = Decimal(str(v))
        else:
            setattr(scene, k, v)
    await session.commit()
    await session.refresh(scene)
    response.headers["ETag"] = _scene_etag(scene)
    return SceneOut.model_validate(scene)


@router.get("/scenes/{scene_id}")
async def get_scene(
    scene_id: uuid.UUID,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SceneOut:
    scene = await _scene_or_404(session, scene_id)
    response.headers["ETag"] = _scene_etag(scene)
    return SceneOut.model_validate(scene)


@router.post("/scenes", status_code=status.HTTP_201_CREATED)
async def create_scene(
    body: SceneCreate,
    session: AsyncSession = Depends(get_session),
) -> SceneOut:
    scene = Scene(
        project_id=body.project_id,
        scene_index=body.scene_index,
        duration_seconds=Decimal(str(body.duration_seconds)),
        visual_prompt=body.visual_prompt,
        narration_script=body.narration_script,
        has_speaker=bool(body.has_speaker),
    )
    session.add(scene)
    await session.commit()
    await session.refresh(scene)
    return SceneOut.model_validate(scene)


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(
    scene_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    scene = await _scene_or_404(session, scene_id)
    await session.delete(scene)
    await session.commit()


@router.post("/scenes/{scene_id}/move")
async def move_scene(
    scene_id: uuid.UUID,
    body: SceneMoveBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Re-order a scene to `new_index`. Performs a full re-numbering inside one
    transaction to satisfy the UNIQUE(project_id, scene_index) constraint —
    setting `scene_index` directly would collide with whatever scene already
    holds that slot.
    """
    scene = await _scene_or_404(session, scene_id)
    project_id = scene.project_id
    old_index = scene.scene_index
    new_index = body.new_index

    # Pull all sibling scenes ordered by current scene_index.
    res = await session.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_index)
    )
    scenes = list(res.scalars().all())
    if not scenes:
        raise HTTPException(status_code=404, detail="no scenes for project")

    new_index = max(1, min(len(scenes), int(new_index)))
    if new_index == old_index:
        return {"ok": True, "scene_id": str(scene_id), "new_index": new_index, "noop": True}

    ordered = [s for s in scenes if s.id != scene_id]
    ordered.insert(new_index - 1, scene)

    # Two-phase update: park everyone at large negative indices, then write
    # the new contiguous sequence. Avoids transient UNIQUE collisions.
    for i, s in enumerate(scenes, start=1):
        await session.execute(
            update(Scene).where(Scene.id == s.id).values(scene_index=-(i + 10_000))
        )
    await session.flush()
    for i, s in enumerate(ordered, start=1):
        await session.execute(
            update(Scene).where(Scene.id == s.id).values(scene_index=i)
        )

    await session.commit()
    return {
        "ok": True, "scene_id": str(scene_id),
        "old_index": old_index, "new_index": new_index,
        "reordered": [str(s.id) for s in ordered],
    }


class RegenerateBody(BaseModel):
    """Optional rewrite instruction. When ``instruction`` is set, the
    scene_regen orchestrator rewrites ``visual_prompt`` + ``narration_script``
    via Gemini before the render task is enqueued. When omitted, the existing
    fields are re-rendered as-is (useful for retrying after a transient
    pipeline failure)."""
    instruction: str | None = None


@router.post("/scenes/{scene_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_scene(
    scene_id: uuid.UUID,
    body: RegenerateBody | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    scene = await _scene_or_404(session, scene_id)
    instruction = (body.instruction or "").strip() if body else ""

    rewrite_summary: dict | None = None
    if instruction:
        project_res = await session.execute(
            select(Project).where(Project.id == scene.project_id)
        )
        project = project_res.scalar_one_or_none()
        if project is not None:
            rewrite = await scene_regen.regenerate(
                session=session, project=project,
                scene_id=scene.id, user_modifier=instruction,
            )
            if rewrite is not None:
                rewrite_summary = {
                    "visual_prompt":    rewrite["visual_prompt"],
                    "narration_script": rewrite["narration_script"],
                    "continuity_notes": rewrite["continuity_notes"],
                }

    task_id = send_celery(
        "worker.render.scene",
        str(scene.project_id), str(scene.id), idempotency_key,
    )
    return {
        "job_id": task_id,
        "scene_id": str(scene_id),
        "rewrite": rewrite_summary,
    }


async def _scene_or_404(session: AsyncSession, scene_id: uuid.UUID) -> Scene:
    res = await session.execute(select(Scene).where(Scene.id == scene_id))
    scene = res.scalar_one_or_none()
    if scene is None:
        raise HTTPException(status_code=404, detail="scene not found")
    return scene
