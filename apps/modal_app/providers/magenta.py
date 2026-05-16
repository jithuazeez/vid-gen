"""Magenta RealTime fallback `MusicProvider`.

Selected when `MUSIC_PROVIDER=magenta`. Streaming-first (2 s chunks);
we concat into a single MP3. Architecture.md §11.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from . import MusicProvider


class MagentaProvider:
    name = "magenta"
    revision = os.environ.get("MAGENTA_MODEL_REVISION", "main")

    def synthesize(self, prompt: str, duration_s: float, *, seed: int = 42) -> Path:
        out = Path(tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name)
        try:
            from magenta_rt import MagentaRT  # type: ignore

            mrt = MagentaRT(model_dir="/models/magenta")
            chunks = mrt.generate_stream(
                prompt=prompt, duration=float(duration_s), seed=int(seed),
            )
            with tempfile.TemporaryDirectory() as td:
                paths = []
                for i, audio in enumerate(chunks):
                    p = Path(td) / f"chunk-{i:04d}.wav"
                    audio.save(str(p))
                    paths.append(str(p))
                _concat_to_mp3(paths, out)
        except Exception:
            _write_silent_mp3(out, duration_s)
        return out


def _concat_to_mp3(wavs: list[str], out: Path) -> None:
    if not wavs:
        _write_silent_mp3(out, 1.0)
        return
    list_file = Path(out).with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{p}'" for p in wavs))
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-codec:a", "libmp3lame", "-b:a", "128k", str(out),
        ],
        check=False,
    )
    list_file.unlink(missing_ok=True)


def _write_silent_mp3(out: Path, seconds: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{max(1.0, float(seconds)):.2f}",
            "-codec:a", "libmp3lame", "-b:a", "128k",
            str(out),
        ],
        check=False,
    )


_check: MusicProvider = MagentaProvider()  # type: ignore[assignment]
