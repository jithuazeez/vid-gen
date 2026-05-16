"""Content-hash cache lookups for the worker controller.

Architecture.md §8 ("Idempotency and caching"). Each Modal function ALSO
checks the cache itself before doing GPU work — but the worker uses these
helpers to skip spawning calls entirely when every input is already cached,
shaving cold-start time off retries and language switches.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from worker.db import session_scope
from sqlalchemy import text


# ── Hashing ────────────────────────────────────────────────────────────


def content_hash(payload: dict[str, Any]) -> str:
    """sha256 of canonical-JSON inputs. Must match storage.content_hash on the
    Modal side, otherwise cache hits won't line up.
    """
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ── Cache lookups ──────────────────────────────────────────────────────


def find_by_hash(content_hash_value: str) -> dict[str, Any] | None:
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT id, project_id, scene_id, asset_type, language, "
                "storage_key FROM assets WHERE content_hash = :h"
            ),
            {"h": content_hash_value},
        ).mappings().first()
        return dict(row) if row else None


def find_asset(
    *,
    project_id: str,
    scene_id: str | None,
    asset_type: str,
    language: str | None,
) -> dict[str, Any] | None:
    """Most-recent matching asset for (project, scene, type, language)."""
    with session_scope() as s:
        row = s.execute(
            text(
                """
                SELECT id, storage_key, content_hash, language
                FROM assets
                WHERE project_id = :pid
                  AND (CAST(:sid AS uuid) IS NULL OR scene_id = CAST(:sid AS uuid))
                  AND asset_type = :at
                  AND (language = :lang OR (language IS NULL AND :lang IS NULL))
                ORDER BY created_at DESC LIMIT 1
                """
            ),
            {"pid": project_id, "sid": scene_id, "at": asset_type, "lang": language},
        ).mappings().first()
        return dict(row) if row else None


# ── Per-stage hash inputs (canonical) ──────────────────────────────────


def scene_video_hash(scene: dict[str, Any], model_revision: str = "ltxv-13b-0.9.7-distilled-fp8") -> str:
    return content_hash({
        "scene_id": str(scene["id"]),
        "visual_prompt": scene.get("visual_prompt", ""),
        "duration_s": float(scene.get("duration_seconds") or 6.0),
        "model": model_revision,
        "seed": int(scene.get("seed") or 42),
    })


def music_hash(project: dict[str, Any], prompt: str, provider: str, revision: str) -> str:
    return content_hash({
        "prompt": prompt,
        "duration_s": float(project.get("duration_seconds") or 30),
        "provider": provider,
        "revision": revision,
        "seed": int(project.get("seed") or 42),
    })


def voice_hash(scene: dict[str, Any], language: str, text_value: str, tone: str) -> str:
    return content_hash({
        "scene_id": str(scene["id"]),
        "language": language,
        "text": text_value,
        "tone": tone,
        "model": "bulbul:v2",
    })


def subtitle_hash(scene_id: str, language: str) -> str:
    return content_hash({
        "scene_id": scene_id, "language": language, "model": "whisper-large-v3",
    })


def composite_hash(scene_id: str, language: str) -> str:
    return content_hash({"scene_id": scene_id, "language": language, "stage": "composite"})


# ── Convenience: skip-spawn predicate used by the controller ───────────


def is_cached(content_hash_value: str) -> bool:
    return find_by_hash(content_hash_value) is not None
