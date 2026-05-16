"""MuseTalk lip-sync loader. Gated by `scene.has_speaker` upstream so this
function only runs when the scene actually has a person speaking on camera.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_inferer: Any = None


def load():
    global _inferer
    if _inferer is not None:
        return _inferer
    try:
        # MuseTalk is shipped as a script project, not a clean package — most
        # deployments end up wrapping their `inference.py` entry point. We
        # construct a thin callable here.
        from musetalk.inference import MuseTalkInference  # type: ignore

        _inferer = MuseTalkInference(model_dir="/models/musetalk", device="cuda")
    except Exception:
        _inferer = None
    return _inferer


def sync(scene_video_path: str, voice_audio_path: str) -> Path:
    """Run MuseTalk lip-sync, returning a path to the sync'd MP4.

    Falls back to copying the source video (silent re-mux) when MuseTalk
    isn't available, so the composite stage still has an input.
    """
    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
    inf = load()
    if inf is None:
        _passthrough(scene_video_path, voice_audio_path, out)
        return out
    try:
        inf.run(
            video_path=scene_video_path,
            audio_path=voice_audio_path,
            output_path=str(out),
        )
    except Exception:
        _passthrough(scene_video_path, voice_audio_path, out)
    return out


def _passthrough(video: str, audio: str, out: Path) -> None:
    """Mux the voice onto the silent scene video without lip-sync."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", video, "-i", audio,
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(out),
        ],
        check=False,
    )
    if not out.exists() or out.stat().st_size == 0:
        shutil.copy(video, out)
