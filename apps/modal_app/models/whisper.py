"""Whisper large-v3 forced-alignment loader.

Used by `subtitles.py` to align the narration script word-by-word against
the synthesized voice track in each language.

Errors propagate. Set ``WHISPER_ALLOW_STUB=1`` to opt back into the offline
stub for local dev without a GPU.
"""
from __future__ import annotations

import os
from typing import Any

_model: Any = None


def load(language: str = "en"):
    global _model
    if _model is not None:
        return _model
    from faster_whisper import WhisperModel  # type: ignore

    _model = WhisperModel(
        os.environ.get("WHISPER_MODEL_SIZE", "large-v3"),
        device=os.environ.get("WHISPER_DEVICE", "cuda"),
        compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "float16"),
        download_root="/models/whisper",
    )
    return _model


def transcribe(audio_path: str, language: str) -> list[dict]:
    """Return word-level timestamps as [{start, end, text}, ...]."""
    if os.environ.get("WHISPER_ALLOW_STUB") == "1":
        try:
            model = load(language)
        except Exception:
            return _stub_words(audio_path)
    else:
        model = load(language)

    segments, _info = model.transcribe(
        audio_path,
        language=_to_whisper_lang(language),
        word_timestamps=True,
        vad_filter=True,
    )
    words: list[dict] = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({"start": float(w.start or 0), "end": float(w.end or 0), "text": w.word.strip()})
    if not words:
        raise RuntimeError(
            f"Whisper returned zero words for {audio_path} (lang={language}). "
            "Audio is likely empty or unintelligible."
        )
    return words


_LANG_MAP = {"en": "en", "hi": "hi", "mr": "mr", "ta": "ta", "pa": "pa"}


def _to_whisper_lang(code: str) -> str:
    return _LANG_MAP.get(code, code)


def _stub_words(audio_path: str) -> list[dict]:
    """Offline stub — only used when WHISPER_ALLOW_STUB=1."""
    try:
        import wave
        with wave.open(audio_path, "rb") as w:
            duration = w.getnframes() / float(w.getframerate())
    except Exception:
        duration = 5.0
    n = 8
    step = max(0.25, duration / n)
    return [
        {"start": i * step, "end": (i + 1) * step, "text": "·"}
        for i in range(n)
    ]
