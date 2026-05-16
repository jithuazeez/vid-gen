"""Whisper large-v3 forced alignment + SRT writer + face-aware position.

This single function combines the Whisper align + MediaPipe face hints
described in architecture.md §8 — they share inputs (the synthesized
voice + scene video) and produce one logical asset (the SRT).
"""
from __future__ import annotations

import os

import math
import tempfile
from pathlib import Path

from .. import storage as st
from . import _common as cc

WHISPER_MODEL = "whisper-large-v3"


def run(project_id: str, scene_id: str, language: str) -> dict:
    h = st.content_hash({
        "scene_id": scene_id, "language": language, "model": WHISPER_MODEL,
        "v": os.environ.get("CACHE_VERSION", "v3"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "subtitle_srt", "scene_id": scene_id,
                    "language": language, "percent": 100, "cache_hit": True})
        return cached

    voice = cc.fetch_asset_by_type(
        project_id=project_id, scene_id=scene_id,
        asset_type="voice", language=language,
    )
    if not voice:
        return {"asset_id": None, "error": "voice asset missing"}

    voice_path = cc.download_to_tmp(voice["storage_key"])

    from ..models import whisper

    words = whisper.transcribe(voice_path, language)
    cues = _words_to_cues(words, max_chars=42, max_lines=2)

    # Face hint for subtitle vertical placement (auto only).
    position_hint = "bottom"
    sv = cc.fetch_asset_by_type(
        project_id=project_id, scene_id=scene_id,
        asset_type="scene_video", language=None,
    )
    if sv:
        from ..models import mediapipe_face

        sv_path = cc.download_to_tmp(sv["storage_key"])
        position_hint = mediapipe_face.detect(sv_path).get("position_hint", "bottom")

    srt = _to_srt(cues)
    out = Path(tempfile.NamedTemporaryFile(suffix=".srt", delete=False).name)
    out.write_text(srt, encoding="utf-8")

    key = st.asset_key(project_id=project_id, asset_type="subtitle_srt",
                       short_hash=h[:8], extension="srt",
                       scene_index=scene_id, language=language)
    bytes_ = st.upload_file(out, key, "application/x-subrip")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="subtitle_srt", language=language,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="application/x-subrip",
        metadata={"model": WHISPER_MODEL, "cues": cues,
                  "generated_position": position_hint},
    )
    _upsert_subtitles_row(scene_id, language, cues, position_hint)
    cc.publish(project_id, "asset_progress",
               {"asset_type": "subtitle_srt", "scene_id": scene_id,
                "language": language, "percent": 100,
                "asset_id": record.get("asset_id"),
                "position_hint": position_hint})
    return record


# ── Word → cue grouping ────────────────────────────────────────────────


def _words_to_cues(words: list[dict], max_chars: int, max_lines: int) -> list[dict]:
    cues: list[dict] = []
    cur: list[str] = []
    cur_start: float | None = None
    cur_end: float = 0.0

    def flush():
        nonlocal cur, cur_start, cur_end
        if cur and cur_start is not None:
            cues.append({"start": cur_start, "end": cur_end, "text": " ".join(cur)})
        cur, cur_start, cur_end = [], None, 0.0

    for w in words:
        if cur_start is None:
            cur_start = float(w["start"])
        prospective = " ".join(cur + [w["text"]])
        if len(prospective) > max_chars * max_lines:
            flush()
            cur_start = float(w["start"])
        cur.append(w["text"])
        cur_end = float(w["end"])
    flush()
    return cues


def _to_srt(cues: list[dict]) -> str:
    out: list[str] = []
    for i, cue in enumerate(cues, start=1):
        out.append(str(i))
        out.append(f"{_ts(cue['start'])} --> {_ts(cue['end'])}")
        out.append(cue["text"])
        out.append("")
    return "\n".join(out)


def _ts(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _upsert_subtitles_row(
    scene_id: str, language: str,
    cues: list[dict], position: str,
) -> None:
    """Mirror the cues into the `subtitles` table for the editor UI."""
    import json
    import os
    import psycopg

    db_url = os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://") \
                   .replace("postgresql+psycopg://", "postgresql://")
    if not db_url:
        return
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subtitles (scene_id, language, cues, generated_position)
                    VALUES (%s, %s, %s::jsonb, %s)
                    ON CONFLICT (scene_id, language) DO UPDATE
                    SET cues = EXCLUDED.cues,
                        generated_position = EXCLUDED.generated_position
                    """,
                    (scene_id, language, json.dumps(cues), position),
                )
                conn.commit()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "_upsert_subtitles_row failed for scene=%s lang=%s: %s",
            scene_id, language, exc,
        )
