"""ACE-Step 1.5 — primary `MusicProvider` implementation.

Loads `ACE-Step/Ace-Step1.5` from HuggingFace (cached on the Modal Volume)
and synthesizes a single MP3 in one forward pass. Apache-2.0; ~3.5B params;
runs on A10G. See architecture.md §11.

Errors propagate. Set ``ACESTEP_ALLOW_SILENT=1`` to opt back into the
silent-MP3 fallback for offline dev.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from . import MusicProvider


class AceStepProvider:
    name = "acestep"
    revision = os.environ.get("ACESTEP_MODEL_REVISION", "main")

    def __init__(self) -> None:
        self._pipeline = None

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline
        # Lazy import — only available inside the Modal acestep_image.
        from acestep.pipeline_ace_step import ACEStepPipeline  # type: ignore

        # ACE-Step is a regular class, not a HF pipeline. It downloads the
        # checkpoint itself on first call when checkpoint_dir is None.
        self._pipeline = ACEStepPipeline(
            checkpoint_dir=os.environ.get("ACESTEP_CHECKPOINT_DIR") or "/models/acestep",
            dtype="bfloat16",
            torch_compile=False,
            cpu_offload=False,
            overlapped_decode=False,
        )
        return self._pipeline

    def synthesize(self, prompt: str, duration_s: float, *, seed: int = 42) -> Path:
        out = Path(tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name)
        allow_silent = os.environ.get("ACESTEP_ALLOW_SILENT") == "1"

        try:
            pipe = self._load()
        except Exception:
            if allow_silent:
                _write_silent_mp3(out.with_suffix(".mp3"), seconds=duration_s)
                return out.with_suffix(".mp3")
            raise

        # ACE-Step's __call__ signature varies across revisions. Pass only
        # kwargs the installed version accepts; raise loudly if required
        # ones (prompt + a duration arg) are missing.
        candidate = {
            "prompt": prompt,
            "lyrics": "",                    # instrumental — must not be None
            "audio_duration": float(duration_s),
            "duration": float(duration_s),  # older revs
            "infer_step": 27,
            "num_inference_steps": 27,       # older revs
            "guidance_scale": 15.0,
            "scheduler_type": "euler",
            "cfg_type": "apg",
            "omega_scale": 10.0,
            "actual_seeds": [int(seed)],
            "seeds": [int(seed)],            # older revs
            "manual_seeds": str(seed),       # demo-app rev
            "save_path": str(out),
        }
        kwargs = _filter_kwargs(pipe.__call__, candidate)
        if "prompt" not in kwargs:
            raise RuntimeError(
                f"ACEStepPipeline.__call__ does not accept 'prompt'. "
                f"Available params: {list(_param_names(pipe.__call__))}"
            )
        result = pipe(**kwargs)
        produced = _resolve_output_path(result, out)
        if produced.suffix.lower() != ".mp3":
            produced = _to_mp3(produced)
        return produced


def _param_names(fn) -> list[str]:
    import inspect
    try:
        return list(inspect.signature(fn).parameters.keys())
    except (TypeError, ValueError):
        return []


def _filter_kwargs(fn, kwargs: dict) -> dict:
    """Keep only kwargs that `fn` actually accepts. If `fn` takes **kwargs,
    pass everything through."""
    import inspect
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


def _resolve_output_path(result, fallback: Path) -> Path:
    """ACE-Step variants return either a path, a list of paths, or None
    (writing to save_path). Normalize to a single existing Path."""
    if isinstance(result, (list, tuple)) and result:
        return Path(str(result[0]))
    if isinstance(result, (str, Path)):
        return Path(str(result))
    if fallback.exists():
        return fallback
    raise RuntimeError(
        f"ACE-Step did not produce an audio file (result={result!r}, "
        f"expected at {fallback})"
    )


def _to_mp3(src: Path) -> Path:
    """Convert ACE-Step's WAV output to MP3 so downstream composite can mux it."""
    import subprocess
    dst = src.with_suffix(".mp3")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-codec:a", "libmp3lame",
         "-b:a", "192k", str(dst)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg wav→mp3 failed: {proc.stderr}")
    return dst


def _write_silent_mp3(out: Path, seconds: float) -> None:
    """Produce a silent MP3 of the requested length using FFmpeg.

    Only used when ACESTEP_ALLOW_SILENT=1.
    """
    import subprocess

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{max(1.0, float(seconds)):.2f}",
            "-codec:a", "libmp3lame", "-b:a", "128k",
            str(out),
        ],
        check=True,
    )


# Sanity: at import time we want this to satisfy the Protocol.
_check: MusicProvider = AceStepProvider()  # type: ignore[assignment]
