"""Audio helpers — duration probe + scene-length alignment.

Sarvam TTS produces a WAV whose length is dictated by the text; the
scene video, by contrast, is rendered to a fixed `duration_seconds`. If
the two drift apart, the composite step either truncates the narration
(audio > video) or leaves silent video tail (audio < video). This module
brings them into agreement before composite ever runs.

Strategy:
  - audio > scene_len → speed up with `atempo`, capped at 1.25× so the
    voice doesn't get chipmunky. Trim trailing silence first to claw
    back a little headroom before applying the cap.
  - audio < scene_len → pad with trailing silence to scene_len. Slowing
    dialogue down with `atempo<1.0` sounds drunk, so we pad instead.
  - |audio - scene_len| ≤ 0.15s → leave as-is.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ATEMPO_MAX = 1.25
TOLERANCE_S = 0.15


def probe_duration(path: str) -> float:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    out = proc.stdout.strip()
    return float(out) if out else 0.0


def _ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\nstderr:\n{proc.stderr}")


def _trim_trailing_silence(in_path: str) -> str:
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _ffmpeg([
        "-i", in_path,
        "-af", "areverse,silenceremove=start_periods=1:start_silence=0:start_threshold=-50dB,areverse",
        out,
    ])
    return out


def _atempo(in_path: str, ratio: float) -> str:
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _ffmpeg(["-i", in_path, "-filter:a", f"atempo={ratio:.4f}", out])
    return out


def _pad_to(in_path: str, target_s: float) -> str:
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _ffmpeg(["-i", in_path, "-af", f"apad=whole_dur={target_s:.3f}", out])
    return out


def align_to_duration(in_path: str, target_s: float) -> tuple[str, dict]:
    """Return (aligned_path, metadata). Metadata records what happened so
    the caller can persist it on the asset row for debugging."""
    cur = probe_duration(in_path)
    if target_s <= 0:
        return in_path, {"action": "skip", "reason": "non-positive target"}

    delta = cur - target_s
    if abs(delta) <= TOLERANCE_S:
        return in_path, {"action": "noop", "audio_s": cur, "target_s": target_s}

    if delta > 0:
        # Audio too long. Trim trailing silence, then speed up if needed.
        trimmed = _trim_trailing_silence(in_path)
        after_trim = probe_duration(trimmed)
        if after_trim - target_s <= TOLERANCE_S:
            return trimmed, {"action": "silence_trim", "audio_s": after_trim,
                             "target_s": target_s}
        ratio = min(ATEMPO_MAX, after_trim / target_s)
        sped = _atempo(trimmed, ratio)
        return sped, {"action": "atempo", "ratio": ratio,
                      "audio_s": probe_duration(sped),
                      "target_s": target_s,
                      "capped": ratio >= ATEMPO_MAX - 1e-6}

    # Audio too short → pad with trailing silence.
    padded = _pad_to(in_path, target_s)
    return padded, {"action": "pad", "audio_s": probe_duration(padded),
                    "target_s": target_s}
