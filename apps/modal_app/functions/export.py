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
        # Bumped to v4 when scene-to-scene xfade transitions landed.
        "v": os.environ.get("CACHE_VERSION", "v4"),
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
    # Explainer projects need hard cuts — crossfading lipsync produces a
    # smeared face. Detect via any scene's brief; composites for explainer
    # scenes don't carry a transition runway anyway.
    use_xfade = not _is_explainer_project(project_id)
    if use_xfade and len(local_paths) >= 2:
        try:
            _ffmpeg_xfade_concat(local_paths, out, quality)
        except Exception as e:
            print(f"[final_export] xfade chain failed ({e}); falling back to plain concat")
            _ffmpeg_concat(local_paths, out, quality)
    else:
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


# Crossfade duration in seconds. Matches the transition runway tail
# rendered by scene_video.run() so the second half of each scene's
# runway becomes the first half of the next scene's opening.
XFADE_DURATION_S = 0.5


def _is_explainer_project(project_id: str) -> bool:
    import psycopg
    from psycopg.rows import dict_row

    db_url = os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://") \
                   .replace("postgresql+psycopg://", "postgresql://")
    if not db_url:
        return False
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brief->>'video_type' AS video_type FROM projects WHERE id = %s",
                (project_id,),
            )
            row = cur.fetchone()
            return bool(row and row.get("video_type") == "explainer")


def _probe_duration(path: str) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    out = proc.stdout.strip()
    return float(out) if out else 0.0


def _ffmpeg_xfade_concat(paths: list[str], out: Path, quality: str) -> None:
    """Chain composites with ffmpeg xfade + acrossfade.

    Each step crossfades the running accumulator with the next composite.
    The xfade `offset` is the running cumulative duration minus the
    crossfade length. If any pair is too short for the crossfade we bail
    and let the caller fall back to plain concat.
    """
    durations = [_probe_duration(p) for p in paths]
    xfd = XFADE_DURATION_S
    if any(d <= xfd + 0.1 for d in durations):
        raise RuntimeError("scene too short for xfade")

    crf = "20" if quality == "1080p" else "23"
    target_h = 1080 if quality == "1080p" else 720

    inputs: list[str] = []
    for p in paths:
        inputs += ["-i", p]

    # Normalise every input to the target height + a uniform SAR so xfade
    # accepts them (mismatched frame dims raise "Width/height not matching").
    filters: list[str] = []
    for i in range(len(paths)):
        filters.append(
            f"[{i}:v]scale=-2:{target_h},setsar=1,fps=24,format=yuv420p[v{i}]"
        )
        filters.append(f"[{i}:a]aresample=async=1:first_pts=0[a{i}]")

    # Chain xfade/acrossfade pairwise.
    cum = durations[0]
    v_prev, a_prev = "v0", "a0"
    for i in range(1, len(paths)):
        offset = cum - xfd
        v_out = f"vx{i}"
        a_out = f"ax{i}"
        filters.append(
            f"[{v_prev}][v{i}]xfade=transition=fade:duration={xfd}:"
            f"offset={offset:.3f}[{v_out}]"
        )
        filters.append(
            f"[{a_prev}][a{i}]acrossfade=d={xfd}[{a_out}]"
        )
        v_prev, a_prev = v_out, a_out
        # Output length after this xfade step = cum + next - xfd.
        cum = cum + durations[i] - xfd

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", f"[{v_prev}]", "-map", f"[{a_prev}]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-crf", crf,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg xfade concat failed (exit {proc.returncode}):\n"
            f"stderr:\n{proc.stderr[-2000:]}"
        )


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
