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

        self._pipeline = ACEStepPipeline.from_pretrained(
            "ACE-Step/Ace-Step1.5",
            revision=self.revision,
            torch_dtype="float16",
            cache_dir="/models/acestep",
        ).to("cuda")
        return self._pipeline

    def synthesize(self, prompt: str, duration_s: float, *, seed: int = 42) -> Path:
        out = Path(tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name)
        allow_silent = os.environ.get("ACESTEP_ALLOW_SILENT") == "1"

        try:
            pipe = self._load()
        except Exception:
            if allow_silent:
                _write_silent_mp3(out, seconds=duration_s)
                return out
            raise

        audio = pipe(
            prompt=prompt,
            duration=float(duration_s),
            seed=int(seed),
            guidance_scale=7.5,
            num_inference_steps=40,
        )
        audio.save(str(out))
        return out


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
