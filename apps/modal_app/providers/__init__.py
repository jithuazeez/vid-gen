"""Provider adapters for external APIs and pluggable model backends.

The `MusicProvider` Protocol lets us swap ACE-Step 1.5 (primary) for
Magenta RealTime (fallback) without touching the pipeline. Sarvam +
Gemini wrappers are normal classes consumed by the leaf workers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class MusicProvider(Protocol):
    """A pluggable music synthesis backend.

    Implementations live in `apps/modal_app/providers/<name>.py` and are
    selected by the `MUSIC_PROVIDER` env var inside the `music.py` Modal
    function.
    """

    name: str
    revision: str

    def synthesize(self, prompt: str, duration_s: float, *, seed: int = 42) -> Path:
        """Synthesize an instrumental track of approximately `duration_s` seconds.

        Returns a local filesystem path to a single MP3 file (no chunk concat
        — caller writes the file straight to S3).
        """
        ...
