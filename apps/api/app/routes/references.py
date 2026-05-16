"""User-uploaded reference assets.

Endpoints:
  POST   /projects/{project_id}/references   — upload one image + ingest
  GET    /projects/{project_id}/references   — list all references
  DELETE /references/{asset_id}              — remove one

References are stored as ``Asset`` rows with ``asset_type`` set to
``character_ref_upload`` / ``style_ref_upload`` / ``environment_ref_upload``
(distinct from SDXL-generated ``character_ref`` rows so the two streams
don't collide). The Gemini-produced descriptor JSON lives on
``asset_metadata["descriptors"]`` and is consumed by ``scene_regen.py``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage as st
from app.db import get_session
from app.db.models import Asset, Project
from app.orchestrators import reference_ingest

router = APIRouter(tags=["references"])

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {
    "image/jpeg": "jpg",
    "image/png":  "png",
    "image/webp": "webp",
}

Kind = Literal["character", "style", "environment"]

ASSET_TYPE_FOR_KIND: dict[Kind, str] = {
    "character":   "character_ref_upload",
    "style":       "style_ref_upload",
    "environment": "environment_ref_upload",
}


class ReferenceOut(BaseModel):
    id: uuid.UUID
    asset_type: str
    kind: Kind
    character_name: str | None
    storage_key: str
    mime_type: str | None
    bytes: int | None
    descriptors: dict[str, Any] | None
    signed_url: str
    expires_at: datetime


# ── POST /projects/{project_id}/references ────────────────────────────


@router.post(
    "/projects/{project_id}/references",
    response_model=ReferenceOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reference(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    kind: Kind = Form(...),
    character_name: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> ReferenceOut:
    project = await _project_or_404(session, project_id)

    if kind == "character" and not (character_name and character_name.strip()):
        raise HTTPException(
            status_code=422,
            detail="character references require a character_name form field",
        )

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported image type {mime!r}; accept JPEG, PNG, or WebP",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty upload")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"file too large; max {MAX_BYTES} bytes")

    content_hash = st.bytes_hash(data)

    # Dedupe within the project: if the same image was uploaded for the same
    # (kind, character_name), return the existing asset rather than
    # re-uploading and re-ingesting.
    existing_res = await session.execute(
        select(Asset).where(Asset.content_hash == content_hash)
    )
    existing = existing_res.scalar_one_or_none()
    if existing is not None and existing.project_id == project_id:
        return _to_out(existing)

    asset_type = ASSET_TYPE_FOR_KIND[kind]
    extension = ALLOWED_MIME[mime]
    key = st.asset_key(
        project_id=str(project_id),
        asset_type=asset_type,
        short_hash=content_hash[:8],
        extension=extension,
    )
    bytes_written = st.put_bytes(key, data, content_type=mime)

    descriptors = reference_ingest.ingest(image_bytes=data, mime_type=mime, kind=kind)

    metadata: dict[str, Any] = {
        "kind": kind,
        "character_name": character_name,
        "descriptors": descriptors,
        "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    asset = Asset(
        project_id=project_id,
        scene_id=None,
        asset_type=asset_type,
        language=None,
        storage_key=key,
        content_hash=content_hash,
        bytes=bytes_written,
        mime_type=mime,
        asset_metadata=metadata,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return _to_out(asset)


# ── GET /projects/{project_id}/references ─────────────────────────────


@router.get("/projects/{project_id}/references", response_model=list[ReferenceOut])
async def list_references(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ReferenceOut]:
    await _project_or_404(session, project_id)
    res = await session.execute(
        select(Asset)
        .where(Asset.project_id == project_id)
        .where(Asset.asset_type.in_(list(ASSET_TYPE_FOR_KIND.values())))
        .order_by(Asset.created_at.desc())
    )
    return [_to_out(a) for a in res.scalars().all()]


# ── DELETE /references/{asset_id} ─────────────────────────────────────


@router.delete("/references/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reference(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    res = await session.execute(select(Asset).where(Asset.id == asset_id))
    asset = res.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="reference not found")
    if asset.asset_type not in ASSET_TYPE_FOR_KIND.values():
        raise HTTPException(status_code=400, detail="not a user-uploaded reference")
    # Best-effort S3 delete; ignore failures so the row goes away regardless.
    try:
        st.s3_client().delete_object(
            Bucket=st.settings.s3_bucket, Key=asset.storage_key,
        )
    except Exception:
        pass
    await session.delete(asset)
    await session.commit()


# ── Helpers ───────────────────────────────────────────────────────────


async def _project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    res = await session.execute(select(Project).where(Project.id == project_id))
    project = res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _to_out(asset: Asset) -> ReferenceOut:
    meta = asset.asset_metadata or {}
    kind = meta.get("kind") or _kind_from_asset_type(asset.asset_type)
    ttl = 3600
    return ReferenceOut(
        id=asset.id,
        asset_type=asset.asset_type,
        kind=kind,  # type: ignore[arg-type]
        character_name=meta.get("character_name"),
        storage_key=asset.storage_key,
        mime_type=asset.mime_type,
        bytes=asset.bytes,
        descriptors=meta.get("descriptors"),
        signed_url=st.signed_get_url(asset.storage_key, ttl_seconds=ttl),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=ttl),
    )


def _kind_from_asset_type(asset_type: str) -> Kind:
    for k, v in ASSET_TYPE_FOR_KIND.items():
        if v == asset_type:
            return k
    return "character"  # safe fallback
