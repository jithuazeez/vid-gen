"""S3 helpers — signed URLs, key construction, content-hash addressing.

Architecture.md §14. Single bucket, content-addressed keys.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config

from app.settings import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def s3_client():
    kwargs: dict[str, Any] = {
        "region_name": settings.s3_region,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def content_hash(payload: dict[str, Any]) -> str:
    """sha256 of canonical JSON of the input payload. Used to dedupe assets."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def asset_key(
    *,
    project_id: str,
    asset_type: str,
    short_hash: str,
    extension: str,
    scene_index: int | None = None,
    language: str | None = None,
    character_id: str | None = None,
) -> str:
    """Return the S3 key for an asset, matching architecture.md §14 layout."""
    base = f"projects/{project_id}"
    match asset_type:
        case "thumbnail":
            return f"{base}/thumbnails/{scene_index}-{short_hash}.{extension}"
        case "character_ref":
            return f"{base}/character_refs/{character_id}-{short_hash}.{extension}"
        case "scene_video":
            return f"{base}/scene_videos/{scene_index}-{short_hash}.{extension}"
        case "music":
            return f"{base}/music/main-{short_hash}.{extension}"
        case "voice":
            return f"{base}/voices/{language}/{scene_index}-{short_hash}.{extension}"
        case "lipsync_video":
            return f"{base}/lipsync/{language}/{scene_index}-{short_hash}.{extension}"
        case "subtitle_srt":
            return f"{base}/subtitles/{language}/{scene_index}-{short_hash}.{extension}"
        case "composite":
            return f"{base}/composites/{language}/{scene_index}-{short_hash}.{extension}"
        case "final_export":
            return f"{base}/exports/{language}/final-{short_hash}.{extension}"
        case "character_ref_upload" | "style_ref_upload" | "environment_ref_upload":
            return f"{base}/references/{asset_type}/{short_hash}.{extension}"
        case _:
            return f"{base}/{asset_type}/{short_hash}.{extension}"


def signed_get_url(key: str, ttl_seconds: int = 3600) -> str:
    return s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=ttl_seconds,
    )


def signed_put_url(key: str, ttl_seconds: int = 3600, content_type: str | None = None) -> str:
    params: dict[str, Any] = {"Bucket": settings.s3_bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return s3_client().generate_presigned_url(
        "put_object", Params=params, ExpiresIn=ttl_seconds
    )


def put_bytes(key: str, data: bytes, content_type: str | None = None) -> int:
    """Upload raw bytes to S3 and return the byte count."""
    kwargs: dict[str, Any] = {"Bucket": settings.s3_bucket, "Key": key, "Body": data}
    if content_type:
        kwargs["ContentType"] = content_type
    s3_client().put_object(**kwargs)
    return len(data)


def bytes_hash(data: bytes) -> str:
    """sha256 of the raw file bytes — used for upload dedupe."""
    return hashlib.sha256(data).hexdigest()
