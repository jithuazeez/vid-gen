"""Render job state + SSE event stream.

Architecture.md §7. Frontend opens GET /jobs/:id/events and receives:
  event: stage_change   data: {...}
  event: scene_ready    data: {...}
  event: progress       data: {...}
  event: done           data: {...}
  event: error          data: {...}
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.db.models import Asset, RenderJob
from app.schemas import JobOut
from app.sse import subscribe_events

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    result = await session.execute(select(RenderJob).where(RenderJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobOut.model_validate(job)


@router.get("/{job_id}/events")
async def job_events(
    request: Request,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> EventSourceResponse:
    """SSE stream of progress + completion events for a single job.

    Subscribes to Redis channel `project:<project_id>:events`. The job's
    project_id is looked up first so workers can publish without knowing
    which job UUIDs are listening.
    """
    result = await session.execute(select(RenderJob).where(RenderJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    project_id = str(job.project_id)

    # Snapshot current per-asset state so a reconnecting editor can rehydrate
    # its timeline without waiting for the next worker event. This is the
    # "reload mid-render" recovery path.
    asset_res = await session.execute(
        select(Asset).where(Asset.project_id == job.project_id)
    )
    assets_snapshot = [
        {
            "id": str(a.id),
            "scene_id": str(a.scene_id) if a.scene_id else None,
            "asset_type": a.asset_type,
            "language": a.language,
            "status": a.status,
            "progress": a.progress,
        }
        for a in asset_res.scalars().all()
        if a.asset_type in {"scene_video", "voice", "lipsync_video",
                            "subtitle_srt", "composite"}
    ]

    async def event_source() -> AsyncIterator[dict[str, str]]:
        # Replay current job state once so a late subscriber sees something.
        yield {
            "event": "snapshot",
            "data": json.dumps(
                {
                    "status": job.status,
                    "current_stage": job.current_stage,
                    "progress": job.progress,
                    "assets": assets_snapshot,
                }
            ),
        }
        async for evt in subscribe_events(project_id):
            if await request.is_disconnected():
                break
            yield {"event": evt["event"], "data": json.dumps(evt["data"])}
            # Cooperative yield so disconnect detection has a chance.
            await asyncio.sleep(0)

    return EventSourceResponse(event_source(), ping=15)
