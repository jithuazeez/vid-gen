"""GET /assets/:id  →  signed URL.

Architecture.md §7. Frontend never holds AWS credentials; it always goes
through this route to get a 1-hour signed URL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import Asset
from app.storage import signed_get_url

router = APIRouter(prefix="/assets", tags=["assets"])

URL_TTL_SECONDS = 3600


class SignedAsset(BaseModel):
    id: uuid.UUID
    asset_type: str
    language: str | None
    storage_key: str
    mime_type: str | None
    bytes: int | None
    signed_url: str
    expires_at: datetime


@router.get("/{asset_id}", response_model=SignedAsset)
async def get_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SignedAsset:
    result = await session.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")

    return SignedAsset(
        id=asset.id,
        asset_type=asset.asset_type,
        language=asset.language,
        storage_key=asset.storage_key,
        mime_type=asset.mime_type,
        bytes=asset.bytes,
        signed_url=signed_get_url(asset.storage_key, ttl_seconds=URL_TTL_SECONDS),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=URL_TTL_SECONDS),
    )
