"""S3 / OCI Object Storage helpers for Modal worker functions.

Each leaf worker uploads its artifact, registers it in the `assets` table
(idempotent on `content_hash`), and returns the asset record.

Architecture.md §14.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config


# ── S3 client ──────────────────────────────────────────────────────────

_s3_client = None


def s3():
    global _s3_client
    if _s3_client is None:
        kwargs: dict[str, Any] = {
            "region_name": os.environ.get("S3_REGION", "us-east-1"),
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        if os.environ.get("S3_ENDPOINT_URL"):
            kwargs["endpoint_url"] = os.environ["S3_ENDPOINT_URL"]
        if os.environ.get("AWS_ACCESS_KEY_ID"):
            kwargs["aws_access_key_id"] = os.environ["AWS_ACCESS_KEY_ID"]
            kwargs["aws_secret_access_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]
        _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def bucket() -> str:
    return os.environ.get("S3_BUCKET", "vidplatform")


# ── Hashing + key construction ─────────────────────────────────────────


def content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def asset_key(
    *,
    project_id: str,
    asset_type: str,
    short_hash: str,
    extension: str,
    scene_index: int | str | None = None,
    language: str | None = None,
    character_id: str | None = None,
) -> str:
    base = f"projects/{project_id}"
    if asset_type == "thumbnail":
        return f"{base}/thumbnails/{scene_index}-{short_hash}.{extension}"
    if asset_type == "character_ref":
        return f"{base}/character_refs/{character_id}-{short_hash}.{extension}"
    if asset_type == "scene_video":
        return f"{base}/scene_videos/{scene_index}-{short_hash}.{extension}"
    if asset_type == "music":
        return f"{base}/music/main-{short_hash}.{extension}"
    if asset_type == "voice":
        return f"{base}/voices/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "lipsync_video":
        return f"{base}/lipsync/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "subtitle_srt":
        return f"{base}/subtitles/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "composite":
        return f"{base}/composites/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "final_export":
        return f"{base}/exports/{language}/final-{short_hash}.{extension}"
    return f"{base}/{asset_type}/{short_hash}.{extension}"


def upload_file(local_path: str | Path, key: str, content_type: str | None = None) -> int:
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    s3().upload_file(str(local_path), bucket(), key, ExtraArgs=extra or None)
    return Path(local_path).stat().st_size


def upload_bytes(data: bytes, key: str, content_type: str) -> int:
    s3().put_object(Bucket=bucket(), Key=key, Body=data, ContentType=content_type)
    return len(data)


# ── Asset table registration (idempotent on content_hash) ──────────────


def register_asset(
    *,
    project_id: str,
    scene_id: str | None,
    asset_type: str,
    language: str | None,
    storage_key: str,
    content_hash_value: str,
    bytes_: int | None = None,
    mime_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert (or return existing) row in `assets`. Returns the asset record."""
    import psycopg
    from psycopg.rows import dict_row

    db_url = os.environ.get("DATABASE_URL", "")
    # Async URL → sync libpq URL.
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://") \
                   .replace("postgresql+psycopg://", "postgresql://")
    if not db_url:
        # Modal-only smoke path with no DB — return ephemeral record.
        return {
            "asset_id": str(uuid.uuid4()),
            "storage_key": storage_key,
            "asset_type": asset_type,
            "scene_id": scene_id,
            "language": language,
            "content_hash": content_hash_value,
            "ephemeral": True,
        }

    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, storage_key FROM assets WHERE content_hash = %s",
                (content_hash_value,),
            )
            existing = cur.fetchone()
            if existing:
                return {
                    "asset_id": str(existing["id"]),
                    "storage_key": existing["storage_key"],
                    "asset_type": asset_type,
                    "scene_id": scene_id,
                    "language": language,
                    "content_hash": content_hash_value,
                    "cache_hit": True,
                }
            try:
                cur.execute(
                    """
                    INSERT INTO assets
                      (project_id, scene_id, asset_type, language,
                       storage_key, content_hash, bytes, mime_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        project_id, scene_id, asset_type, language,
                        storage_key, content_hash_value, bytes_, mime_type,
                        json.dumps(metadata or {}),
                    ),
                )
            except psycopg.errors.ForeignKeyViolation as exc:
                raise RuntimeError(
                    f"Project {project_id!r} (or scene {scene_id!r}) does not exist in the "
                    "database that Modal is connected to. Ensure the Modal 'database-url' "
                    "secret points to the same PostgreSQL instance as the API and Celery "
                    "worker, and that migrations have been applied (alembic upgrade head)."
                ) from exc
            row = cur.fetchone()
            conn.commit()
            return {
                "asset_id": str(row["id"]),
                "storage_key": storage_key,
                "asset_type": asset_type,
                "scene_id": scene_id,
                "language": language,
                "content_hash": content_hash_value,
                "cache_hit": False,
            }


def find_cached_asset(content_hash_value: str) -> dict[str, Any] | None:
    """Return the existing asset record if `content_hash` is already in the table."""
    import psycopg
    from psycopg.rows import dict_row

    db_url = os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://") \
                   .replace("postgresql+psycopg://", "postgresql://")
    if not db_url:
        return None
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, project_id, scene_id, asset_type, language, "
                "storage_key, content_hash FROM assets WHERE content_hash = %s",
                (content_hash_value,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "asset_id": str(row["id"]),
                "storage_key": row["storage_key"],
                "asset_type": row["asset_type"],
                "scene_id": str(row["scene_id"]) if row["scene_id"] else None,
                "language": row["language"],
                "content_hash": row["content_hash"],
                "cache_hit": True,
            }
