"""Sync DB session for Celery tasks.

Celery is multi-process; we use a per-task sync session via psycopg3.
The async API service shares the same models/schema via Alembic.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def _sync_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. The Celery worker requires an explicit database URL. "
            "Set DATABASE_URL to the same PostgreSQL connection string used by the API and "
            "the Modal 'database-url' secret (e.g. postgresql://user:pass@host/db)."
        )
    return (
        url.replace("+asyncpg", "+psycopg")
        .replace("postgresql+psycopg2", "postgresql+psycopg")
    )


_engine = create_engine(_sync_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)
_SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────────────
# Minimal data-access helpers used by Celery tasks. Schema mirrors
# apps/api/app/db/models.py — we use raw SQL here to avoid having to
# import the API package from the worker.
# ─────────────────────────────────────────────────────────────────────


def create_job(
    *,
    project_id: str,
    job_type: str,
    language: str | None = None,
    idempotency_key: str | None = None,
) -> str:
    with session_scope() as s:
        row = s.execute(
            text(
                """
                INSERT INTO render_jobs
                  (project_id, job_type, language, status, current_stage, idempotency_key)
                VALUES
                  (:pid, :jt, :lang, 'running', 'queued', :idem)
                RETURNING id
                """
            ),
            {"pid": project_id, "jt": job_type, "lang": language, "idem": idempotency_key},
        ).fetchone()
        return str(row[0])


def start_job(job_id: str) -> None:
    """Transition a pre-created pending job to running."""
    with session_scope() as s:
        s.execute(
            text(
                "UPDATE render_jobs "
                "SET status = 'running', current_stage = 'queued', updated_at = now() "
                "WHERE id = :jid"
            ),
            {"jid": job_id},
        )


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    current_stage: str | None = None,
    progress: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    sets: list[str] = ["updated_at = now()"]
    params: dict[str, Any] = {"jid": job_id}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if current_stage is not None:
        sets.append("current_stage = :stage")
        params["stage"] = current_stage
    if progress is not None:
        sets.append("progress = CAST(:progress AS jsonb)")
        params["progress"] = _to_jsonb_str(progress)
    if error is not None:
        sets.append("error = :error")
        params["error"] = error
    with session_scope() as s:
        s.execute(
            text(f"UPDATE render_jobs SET {', '.join(sets)} WHERE id = :jid"),
            params,
        )


def fetch_project(project_id: str) -> dict[str, Any] | None:
    with session_scope() as s:
        row = s.execute(
            text(
                """
                SELECT id, title, status, brief, primary_language, active_language,
                       available_languages, aspect_ratio, duration_seconds,
                       has_characters, music_enabled, seed
                FROM projects WHERE id = :pid
                """
            ),
            {"pid": project_id},
        ).mappings().first()
        return dict(row) if row else None


def set_project_status(project_id: str, status: str) -> None:
    with session_scope() as s:
        s.execute(
            text("UPDATE projects SET status = :s, updated_at = now() WHERE id = :pid"),
            {"s": status, "pid": project_id},
        )


def append_available_language(project_id: str, language: str) -> None:
    with session_scope() as s:
        s.execute(
            text(
                """
                UPDATE projects
                SET available_languages = array(
                  SELECT DISTINCT unnest(available_languages || ARRAY[:lang])
                ),
                active_language = :lang,
                updated_at = now()
                WHERE id = :pid
                """
            ),
            {"pid": project_id, "lang": language},
        )


def list_scenes(project_id: str) -> list[dict[str, Any]]:
    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT id, scene_index, duration_seconds, visual_prompt,
                       narration_script, has_speaker, subtitle_position,
                       thumbnail_asset_id, scene_video_asset_id
                FROM scenes WHERE project_id = :pid ORDER BY scene_index
                """
            ),
            {"pid": project_id},
        ).mappings().all()
        return [dict(r) for r in rows]


def upsert_scenes(project_id: str, scenes: list[dict[str, Any]]) -> None:
    """Replace the project's scenes with the supplied list."""
    with session_scope() as s:
        s.execute(text("DELETE FROM scenes WHERE project_id = :pid"), {"pid": project_id})
        for i, sc in enumerate(scenes, start=1):
            s.execute(
                text(
                    """
                    INSERT INTO scenes
                      (id, project_id, scene_index, duration_seconds,
                       visual_prompt, narration_script, has_speaker,
                       subtitle_position)
                    VALUES
                      (gen_random_uuid(), :pid, :idx, :dur,
                       :vp, :ns, :hs, :sp)
                    """
                ),
                {
                    "pid": project_id,
                    "idx": sc.get("scene_index", i),
                    "dur": sc["duration_seconds"],
                    "vp": sc["visual_prompt"],
                    "ns": sc["narration_script"],
                    "hs": bool(sc.get("has_speaker", False)),
                    "sp": sc.get("subtitle_position", "auto"),
                },
            )


def register_asset(
    *,
    project_id: str,
    scene_id: str | None,
    asset_type: str,
    language: str | None,
    storage_key: str,
    content_hash: str,
    mime_type: str | None = None,
    bytes_: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Return existing asset_id on content_hash conflict (idempotent)."""
    with session_scope() as s:
        existing = s.execute(
            text("SELECT id FROM assets WHERE content_hash = :h"),
            {"h": content_hash},
        ).fetchone()
        if existing:
            return str(existing[0])
        row = s.execute(
            text(
                """
                INSERT INTO assets
                  (project_id, scene_id, asset_type, language,
                   storage_key, content_hash, bytes, mime_type, metadata,
                   status, progress)
                VALUES
                  (:pid, :sid, :at, :lang, :sk, :ch, :b, :mt, CAST(:md AS jsonb),
                   'ready', 100)
                RETURNING id
                """
            ),
            {
                "pid": project_id,
                "sid": scene_id,
                "at": asset_type,
                "lang": language,
                "sk": storage_key,
                "ch": content_hash,
                "b": bytes_,
                "mt": mime_type,
                "md": _to_jsonb_str(metadata) if metadata else None,
            },
        ).fetchone()
        return str(row[0])


def _to_jsonb_str(d: dict[str, Any] | None) -> str:
    import json
    return json.dumps(d or {})


# ─────────────────────────────────────────────────────────────────────
# Per-asset state machine — feeds the async editor timeline.
# The API seeds slot rows (status='queued') at job kickoff; the worker
# flips them to 'generating' on spawn and 'ready' / 'failed' on terminal
# state. UI subscribes via SSE.
# ─────────────────────────────────────────────────────────────────────


def set_asset_status(
    *,
    project_id: str,
    scene_id: str | None,
    asset_type: str,
    language: str | None,
    status: str,
    progress: int | None = None,
) -> None:
    """Update the slot row matching (project, scene, asset_type, language).
    No-op when no slot exists — keeps the worker robust against old jobs
    that predate slot seeding.
    """
    sets = ["status = :status", "updated_at = now()"]
    params: dict[str, Any] = {
        "pid": project_id, "sid": scene_id,
        "at": asset_type, "lang": language, "status": status,
    }
    if progress is not None:
        sets.append("progress = :prog")
        params["prog"] = max(0, min(100, int(progress)))
    elif status == "ready":
        sets.append("progress = 100")

    where = ["project_id = :pid", "asset_type = :at"]
    if scene_id is None:
        where.append("scene_id IS NULL")
    else:
        where.append("scene_id = :sid")
    if language is None:
        where.append("language IS NULL")
    else:
        where.append("language = :lang")

    with session_scope() as s:
        s.execute(
            text(
                f"UPDATE assets SET {', '.join(sets)} "
                f"WHERE {' AND '.join(where)}"
            ),
            params,
        )


def seed_estimated_subtitle_cues(project_id: str, language: str) -> None:
    """Split each scene's narration_script into rough cues and persist as
    Subtitle rows with source='estimated'. These appear in the editor the
    moment the storyboard is approved; whisper_align overwrites with
    word-accurate timings as each scene's audio finishes.
    """
    import json
    import re

    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT id, duration_seconds, narration_script, has_speaker
                FROM scenes WHERE project_id = :pid ORDER BY scene_index
                """
            ),
            {"pid": project_id},
        ).mappings().all()

        for r in rows:
            if not r["has_speaker"]:
                continue
            script = (r["narration_script"] or "").strip()
            if not script:
                continue
            chunks = [
                p.strip()
                for p in re.split(r"(?<=[.!?])\s+|\n+|,\s+", script)
                if p.strip()
            ]
            if not chunks:
                continue
            dur = float(r["duration_seconds"] or 0) or len(chunks) * 1.5
            per = dur / len(chunks)
            cues = [
                {"start": round(i * per, 2),
                 "end":   round((i + 1) * per, 2),
                 "text":  c}
                for i, c in enumerate(chunks)
            ]
            # Don't clobber a whisper-aligned row if one already exists for
            # this scene+language — the worker may re-run after editing.
            s.execute(
                text(
                    """
                    INSERT INTO subtitles (scene_id, language, cues, source)
                    VALUES (:sid, :lang, CAST(:cues AS jsonb), 'estimated')
                    ON CONFLICT (scene_id, language) DO UPDATE
                      SET cues = EXCLUDED.cues, source = 'estimated'
                      WHERE subtitles.source <> 'whisper'
                    """
                ),
                {"sid": r["id"], "lang": language, "cues": json.dumps(cues)},
            )
