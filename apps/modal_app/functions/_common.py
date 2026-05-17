"""Shared helpers for Modal leaf workers — DB lookups, SSE publish, asset
upload + registration. Keeps the per-function modules tiny.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .. import storage as st


# ── SSE pub/sub (workers PUBLISH; API subscribes) ──────────────────────


def publish(project_id: str, event: str, data: dict[str, Any]) -> None:
    try:
        import redis  # type: ignore

        r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        r.publish(
            f"project:{project_id}:events",
            json.dumps({"event": event, "data": data}),
        )
    except Exception:
        pass


# ── Read-only scene/project lookups ────────────────────────────────────


def fetch_scene(scene_id: str) -> dict[str, Any] | None:
    return _query_one(
        """
        SELECT s.id, s.project_id, s.scene_index, s.duration_seconds,
               s.visual_prompt, s.narration_script, s.has_speaker,
               s.subtitle_position, s.scene_video_asset_id,
               p.primary_language, p.aspect_ratio, p.seed,
               p.brief
        FROM scenes s JOIN projects p ON p.id = s.project_id
        WHERE s.id = %s
        """,
        (scene_id,),
    )


def fetch_project(project_id: str) -> dict[str, Any] | None:
    return _query_one(
        "SELECT id, brief, primary_language, duration_seconds, aspect_ratio, seed FROM projects WHERE id = %s",
        (project_id,),
    )


def fetch_character_ref_hashes(project_id: str) -> list[str]:
    """All character_ref content hashes for a project, sorted for stable hashing.

    Used by scene_video so the cache key changes when the cast does.
    """
    rows = _query_all(
        """
        SELECT content_hash FROM assets
        WHERE project_id = %s AND asset_type = 'character_ref'
        ORDER BY content_hash
        """,
        (project_id,),
    )
    return [r["content_hash"] for r in rows] if rows else []


def fetch_asset_by_type(
    *,
    project_id: str,
    scene_id: str | None,
    asset_type: str,
    language: str | None,
) -> dict[str, Any] | None:
    return _query_one(
        """
        SELECT id, storage_key, content_hash, language
        FROM assets
        WHERE project_id = %s
          AND (%s::uuid IS NULL OR scene_id = %s::uuid)
          AND asset_type = %s
          AND (language = %s::text OR (language IS NULL AND %s::text IS NULL))
          AND status = 'ready'
          AND storage_key != ''
        ORDER BY created_at DESC LIMIT 1
        """,
        (project_id, scene_id, scene_id, asset_type, language, language),
    )


# ── Cache helper used by every worker ──────────────────────────────────


def cached_or(content_hash_value: str):
    """Return cached asset dict if present, else None."""
    return st.find_cached_asset(content_hash_value)


# ── Local download helper for chained pipelines (e.g. compositor) ──────


def download_to_tmp(storage_key: str) -> str:
    import tempfile
    out = tempfile.NamedTemporaryFile(delete=False).name
    st.s3().download_file(st.bucket(), storage_key, out)
    return out


# ── Internal ────────────────────────────────────────────────────────────


def _query_one(sql: str, params: tuple) -> dict[str, Any] | None:
    rows = _query_all(sql, params)
    return rows[0] if rows else None


def _query_all(sql: str, params: tuple) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    db_url = os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://") \
                   .replace("postgresql+psycopg://", "postgresql://")
    if not db_url:
        return []
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
