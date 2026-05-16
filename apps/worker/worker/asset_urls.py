"""Resolve asset_id → signed S3 URL for inclusion in SSE events.

Architecture.md §7: `scene_ready` events must carry `asset_url` so the
frontend can play the preview without a follow-up `GET /assets/:id`
round-trip.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config
from sqlalchemy import text

from worker import db

_TTL = 3600


@lru_cache(maxsize=1)
def _s3():
    kwargs: dict[str, Any] = {
        "region_name": os.environ.get("S3_REGION", "us-east-1"),
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if endpoint := os.environ.get("S3_ENDPOINT_URL"):
        kwargs["endpoint_url"] = endpoint
    if key_id := os.environ.get("AWS_ACCESS_KEY_ID"):
        kwargs["aws_access_key_id"] = key_id
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    return boto3.client("s3", **kwargs)


def signed_url_for_asset(asset_id: str | None) -> str | None:
    if not asset_id:
        return None
    with db.session_scope() as s:
        row = s.execute(
            text("SELECT storage_key FROM assets WHERE id = :aid"),
            {"aid": asset_id},
        ).fetchone()
    if not row:
        return None
    bucket = os.environ.get("S3_BUCKET", "vidplatform")
    try:
        return _s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": row[0]},
            ExpiresIn=_TTL,
        )
    except Exception:
        return None
