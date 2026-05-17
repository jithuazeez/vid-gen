"""MuseTalk lip-sync loader. Gated by `scene.has_speaker` upstream so this
function only runs when the scene actually has a person speaking on camera.

Status: **not currently installed**. The MuseTalk image
(``apps/modal_app/app.py`` ``musetalk_image``) does not pip-install the
``musetalk`` package because it's a script-only project that needs a
manual checkout + mmcv/mmdet/mmpose dance. Until that integration ships,
this module raises loudly instead of silently falling back to an
audio-only re-mux. The old passthrough produced a video where the voice
played but lips never moved, and the worker reported success — that's
worse than a hard failure because it shipped broken artifacts.

To keep the regen pipeline usable in the meantime, the storyboard UI
forces ``has_speaker=False`` on every scene, which skips this call
entirely. When we wire up a real lip-sync model (MuseTalk proper,
LatentSync, Wav2Lip, ...) re-enable the speaker toggle and remove the
guard in ``apps/api/app/orchestrators/scene_engine.py``.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

_inferer: Any = None


class LipSyncNotInstalled(RuntimeError):
    """Raised when a speaker scene reaches musetalk but the model isn't
    available. We intentionally do NOT fall back to a silent passthrough —
    the previous behavior shipped videos where audio played but lips
    didn't move, and surfaced as 'lip-sync isn't working' instead of as
    a clear deploy gap."""


def load():
    global _inferer
    if _inferer is not None:
        return _inferer
    # MuseTalk is a script project, not a clean package; the import below
    # only succeeds if the image was extended to git-clone and `pip install
    # -e` the upstream repo with mmcv/mmdet/mmpose pinned to a torch-2.4
    # compatible matrix. Until that lands, this raises so failures are
    # visible in the Modal dashboard instead of silently emitting an
    # audio-only re-mux.
    from musetalk.inference import MuseTalkInference  # type: ignore

    _inferer = MuseTalkInference(model_dir="/models/musetalk", device="cuda")
    return _inferer


def sync(scene_video_path: str, voice_audio_path: str) -> Path:
    """Run MuseTalk lip-sync, returning a path to the sync'd MP4."""
    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
    try:
        inf = load()
    except Exception as exc:
        raise LipSyncNotInstalled(
            "MuseTalk is not installed in the musetalk_image. The previous "
            "code path silently fell back to muxing audio onto the silent "
            "LTX video, which is why 'lip-sync jobs succeed but lips don't "
            "move'. Install MuseTalk (or swap in LatentSync/Wav2Lip) before "
            "enabling has_speaker on any scene."
        ) from exc

    inf.run(
        video_path=scene_video_path,
        audio_path=voice_audio_path,
        output_path=str(out),
    )
    return out
