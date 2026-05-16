"""FFmpeg per-scene composite.

Inputs (all optional except scene_video):
  - scene_video         (silent MP4 from LTX)
  - lipsync_video       (lip-sync'd MP4 from MuseTalk; replaces scene_video)
  - voice               (WAV from Sarvam Bulbul; muxed onto video if no lipsync)
  - subtitle_srt        (burned in via subtitles filter)
  - music               (project-wide MP3; ducked under voice)

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
    h = st.content_hash({
        "scene_id": scene_id, "language": language, "stage": STAGE,
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
    music = cc.fetch_asset_by_type(project_id=project_id, scene_id=None,
                                    asset_type="music", language=None)

    base_video_key = (lipsync or sv)["storage_key"] if (lipsync or sv) else None
    if not base_video_key:
        return {"asset_id": None, "error": "no scene video"}

    base_video = cc.download_to_tmp(base_video_key)
    voice_path = cc.download_to_tmp(voice["storage_key"]) if voice else None
    srt_path = cc.download_to_tmp(srt["storage_key"]) if srt else None
    music_path = cc.download_to_tmp(music["storage_key"]) if music else None

    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
    _run_ffmpeg(
        video_in=base_video,
        voice_in=voice_path,
        music_in=music_path,
        srt_in=srt_path,
        srt_use_existing_audio=lipsync is not None,
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
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": STAGE, "scene_id": scene_id,
                "language": language, "percent": 100,
                "asset_id": record.get("asset_id")})
    return record


def _run_ffmpeg(
    *, video_in: str, voice_in: str | None, music_in: str | None,
    srt_in: str | None, srt_use_existing_audio: bool, out: str,
) -> None:
    cmd = ["ffmpeg", "-y", "-i", video_in]
    audio_inputs: list[str] = []
    if voice_in:
        cmd += ["-i", voice_in]
        audio_inputs.append(f"{len(audio_inputs) + 1}:a")
    if music_in:
        cmd += ["-i", music_in]
        audio_inputs.append(f"{len(audio_inputs) + 1}:a")

    filters: list[str] = []
    if srt_in:
        # Burn captions; escape single quotes in path for FFmpeg filter parser.
        escaped = srt_in.replace("'", "'\\''")
        filters.append(
            f"[0:v]subtitles='{escaped}':force_style='FontSize=18,Outline=2,"
            f"OutlineColour=&H40000000,BorderStyle=3'[vout]"
        )
    else:
        filters.append("[0:v]copy[vout]")

    audio_label = None
    if voice_in and music_in:
        # Sidechain duck music under voice (-6 dB during voice).
        filters.append(
            "[2:a]volume=-18dB[mbg];"
            "[mbg][1:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=200[mduck];"
            "[1:a][mduck]amix=inputs=2:duration=first:dropout_transition=2,"
            "dynaudnorm=f=200[aout]"
        )
        audio_label = "[aout]"
    elif voice_in:
        filters.append("[1:a]anull[aout]")
        audio_label = "[aout]"
    elif music_in:
        filters.append("[1:a]volume=-18dB[aout]")
        audio_label = "[aout]"
    elif srt_use_existing_audio:
        # No replacement audio; keep whatever was on the video (lipsync includes it).
        audio_label = "0:a?"

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
