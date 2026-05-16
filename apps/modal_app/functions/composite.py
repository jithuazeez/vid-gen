"""FFmpeg per-scene composite.

Inputs (all optional except a base video):
  - scene_video         silent MP4 from LTX-2
  - lipsync_video       lip-sync'd MP4 from MuseTalk; replaces scene_video
                        and carries the voice track muxed in
  - voice               WAV from Sarvam Bulbul (used when has_speaker but
                        lipsync didn't run, e.g. cached pre-lipsync)
  - native_audio        WAV emitted by LTX-2 for non-speaker scenes
  - subtitle_srt        burned in via the subtitles filter

Audio source precedence per scene:
  1. lipsync_video      → keep its embedded audio (voice already muxed)
  2. voice              → mux the TTS wav onto scene_video
  3. native_audio       → mux the LTX-2 audio onto scene_video
  4. silent             → drop audio entirely

Output: composite/{lang}/{scene}-{hash}.mp4
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .. import storage as st
from . import _common as cc

STAGE = "composite"


def run(project_id: str, scene_id: str, language: str) -> dict:
    import os
    h = st.content_hash({
        "scene_id": scene_id, "language": language, "stage": STAGE,
        # Bumped to v4 when music was removed and native_audio joined the
        # precedence ladder.
        "v": os.environ.get("CACHE_VERSION", "v4"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": STAGE, "scene_id": scene_id,
                    "language": language, "percent": 100, "cache_hit": True})
        return cached

    sv = cc.fetch_asset_by_type(project_id=project_id, scene_id=scene_id,
                                 asset_type="scene_video", language=None)
    lipsync = cc.fetch_asset_by_type(project_id=project_id, scene_id=scene_id,
                                      asset_type="lipsync_video", language=language)
    voice = cc.fetch_asset_by_type(project_id=project_id, scene_id=scene_id,
                                    asset_type="voice", language=language)
    srt = cc.fetch_asset_by_type(project_id=project_id, scene_id=scene_id,
                                  asset_type="subtitle_srt", language=language)
    native_audio = cc.fetch_asset_by_type(project_id=project_id, scene_id=scene_id,
                                            asset_type="native_audio", language=None)

    base_video_key = (lipsync or sv)["storage_key"] if (lipsync or sv) else None
    if not base_video_key:
        return {"asset_id": None, "error": "no scene video"}

    base_video = cc.download_to_tmp(base_video_key)
    srt_path = cc.download_to_tmp(srt["storage_key"]) if srt else None

    # Audio source selection — see precedence in the module docstring.
    audio_path: str | None = None
    audio_source: str
    if lipsync is not None:
        audio_path = None
        audio_source = "lipsync"
    elif voice is not None:
        audio_path = cc.download_to_tmp(voice["storage_key"])
        audio_source = "voice"
    elif native_audio is not None:
        audio_path = cc.download_to_tmp(native_audio["storage_key"])
        audio_source = "native"
    else:
        audio_source = "silent"

    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
    _run_ffmpeg(
        video_in=base_video,
        audio_in=audio_path,
        audio_source=audio_source,
        srt_in=srt_path,
        out=str(out),
    )

    key = st.asset_key(project_id=project_id, asset_type=STAGE,
                       short_hash=h[:8], extension="mp4",
                       scene_index=scene_id, language=language)
    bytes_ = st.upload_file(out, key, "video/mp4")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type=STAGE, language=language,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="video/mp4",
        metadata={"audio_source": audio_source},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": STAGE, "scene_id": scene_id,
                "language": language, "percent": 100,
                "asset_id": record.get("asset_id")})
    return record


def _run_ffmpeg(
    *, video_in: str, audio_in: str | None, audio_source: str,
    srt_in: str | None, out: str,
) -> None:
    cmd = ["ffmpeg", "-y", "-i", video_in]
    if audio_in:
        cmd += ["-i", audio_in]

    filters: list[str] = []
    if srt_in:
        # Burn captions; escape single quotes in path for ffmpeg's filter parser.
        escaped = srt_in.replace("'", "'\\''")
        filters.append(
            f"[0:v]subtitles='{escaped}':force_style='FontSize=18,Outline=2,"
            f"OutlineColour=&H40000000,BorderStyle=3'[vout]"
        )
    else:
        filters.append("[0:v]copy[vout]")

    audio_label: str | None
    if audio_source == "lipsync":
        # Voice is already muxed inside the lipsync video.
        audio_label = "0:a?"
    elif audio_in is not None:
        # voice or native_audio — pass through as the sole audio track.
        filters.append("[1:a]anull[aout]")
        audio_label = "[aout]"
    else:
        audio_label = None  # silent output

    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if audio_label:
        cmd += ["-map", audio_label]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "-shortest", out]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg composite failed (exit {proc.returncode}):\n"
            f"cmd: {' '.join(cmd)}\nstderr:\n{proc.stderr}"
        )
