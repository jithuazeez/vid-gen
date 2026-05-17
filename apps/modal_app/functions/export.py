"""Final export: concat all per-scene composites for a language into one MP4.

Quality: 720p / 1080p (CRF tuned per quality).
Subtitles: 'burned' (already burned by composite_scene) | 'sidecar' (copy SRT).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .. import storage as st
from . import _common as cc


def run(
    project_id: str, language: str,
    quality: str = "1080p", subtitles: str = "burned",
) -> dict:
    h = st.content_hash({
        "project_id": project_id, "language": language,
        "quality": quality, "subtitles": subtitles, "stage": "final_export",
        "v": os.environ.get("CACHE_VERSION", "v3"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "stage_change",
                   {"stage": "final_export", "language": language,
                    "percent": 100, "cache_hit": True})
        return cached

    composites = _list_composites(project_id, language)
    if not composites:
        return {"asset_id": None, "error": "no composites"}

    local_paths = [cc.download_to_tmp(c["storage_key"]) for c in composites]
    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
    _ffmpeg_concat(local_paths, out, quality)

    key = st.asset_key(project_id=project_id, asset_type="final_export",
                       short_hash=h[:8], extension="mp4",
                       language=language)
    bytes_ = st.upload_file(out, key, "video/mp4")
    record = st.register_asset(
        project_id=project_id, scene_id=None,
        asset_type="final_export", language=language,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="video/mp4",
        metadata={"quality": quality, "subtitles": subtitles,
                  "scene_count": len(composites)},
    )
    cc.publish(project_id, "stage_change",
               {"stage": "final_export", "language": language,
                "percent": 100, "asset_id": record.get("asset_id")})
    return record


def _list_composites(project_id: str, language: str) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    db_url = os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://") \
                   .replace("postgresql+psycopg://", "postgresql://")
    if not db_url:
        return []
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.storage_key, s.scene_index
                FROM assets a JOIN scenes s ON s.id = a.scene_id
                WHERE a.project_id = %s
                  AND a.asset_type = 'composite'
                  AND a.language = %s
                  AND a.status = 'ready'
                  AND a.storage_key != ''
                ORDER BY s.scene_index ASC
                """,
                (project_id, language),
            )
            return [dict(r) for r in cur.fetchall()]


def _ffmpeg_concat(paths: list[str], out: Path, quality: str) -> None:
    list_file = out.with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{p}'" for p in paths))
    crf = "20" if quality == "1080p" else "23"
    target_h = 1080 if quality == "1080p" else 720
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-vf", f"scale=-2:{target_h}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", crf,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg final concat failed (exit {proc.returncode}):\n"
            f"cmd: {' '.join(cmd)}\nstderr:\n{proc.stderr}"
        )
