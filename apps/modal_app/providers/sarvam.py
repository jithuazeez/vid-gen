"""Sarvam adapter — Bulbul-v2 multilingual TTS + Sarvam Translate.

Both are HTTP APIs; no GPU work. Called from `functions/voice.py` and
indirectly from `functions/subtitles.py` when re-aligning a translated
script in the target language.
"""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

import httpx

SARVAM_BASE = "https://api.sarvam.ai"


# ── Translate ──────────────────────────────────────────────────────────


def translate(text: str, source_lang: str, target_lang: str) -> str:
    """Sarvam Translate v1. Returns translated text."""
    if source_lang == target_lang:
        return text
    api_key = os.environ.get("SARVAM_API_KEY", "")
    if not api_key:
        # Offline fallback — return source so the pipeline can still proceed.
        return text
    r = httpx.post(
        f"{SARVAM_BASE}/translate",
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json={
            "input": text,
            "source_language_code": _to_sarvam_code(source_lang),
            "target_language_code": _to_sarvam_code(target_lang),
            "model": os.environ.get("SARVAM_TRANSLATE_MODEL", "sarvam-translate:v1"),
        },
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(
            f"Sarvam Translate {r.status_code} "
            f"({source_lang}→{target_lang}): {r.text[:500]}"
        )
    return r.json().get("translated_text") or text


# ── Bulbul-v2 TTS ──────────────────────────────────────────────────────


def synthesize_speech(
    text: str,
    language: str,
    *,
    tone: str = "calm",
    speaker: str | None = None,
) -> Path:
    """Generate a WAV file from `text` in the target `language`.

    Returns a path to a temporary WAV file. Caller is responsible for moving
    it to S3 / cleaning it up. Works offline by emitting a 1-second silent
    WAV stub when `SARVAM_API_KEY` isn't set, so the rest of the pipeline
    keeps moving.
    """
    api_key = os.environ.get("SARVAM_API_KEY", "")
    out = Path(tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name)

    if not api_key:
        _write_silence(out, seconds=max(1.0, min(15.0, _estimate_duration(text))))
        return out

    body = {
        "inputs": [text],
        "target_language_code": _to_sarvam_code(language),
        "speaker": speaker or _default_speaker(language, tone),
        "model": os.environ.get("SARVAM_TTS_MODEL", "bulbul:v2"),
        "pitch": 0,
        "pace": _pace_for_tone(tone),
        "loudness": 1.0,
        "speech_sample_rate": 22050,
        "enable_preprocessing": True,
    }
    r = httpx.post(
        f"{SARVAM_BASE}/text-to-speech",
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if r.status_code >= 400:
        # Surface Sarvam's structured error body instead of httpx's
        # opaque "Client error '400 Bad Request'". The body tells us
        # exactly which field (speaker, language code, etc.) was rejected.
        raise RuntimeError(
            f"Sarvam TTS {r.status_code} for speaker={body.get('speaker')!r} "
            f"lang={body.get('target_language_code')!r}: {r.text[:500]}"
        )
    data = r.json()
    audio_b64 = (data.get("audios") or [None])[0]
    if not audio_b64:
        _write_silence(out, seconds=_estimate_duration(text))
        return out
    out.write_bytes(base64.b64decode(audio_b64))
    return out


# ── Helpers ────────────────────────────────────────────────────────────


_LANG_TO_SARVAM = {
    "en": "en-IN", "hi": "hi-IN", "mr": "mr-IN",
    "ta": "ta-IN", "pa": "pa-IN",
}


def _to_sarvam_code(code: str) -> str:
    return _LANG_TO_SARVAM.get(code, code)


# Sarvam Bulbul-v2 speaker catalog as of 2026-05-16. The earlier
# defaults (meera, arjun, amol) were removed/renamed by Sarvam — the
# API now returns 400 "speaker not recognized" for them. Keep this
# list in sync with the message body returned on a bad-speaker error:
#   anushka, abhilash, manisha, vidya, arya, karun, hitesh, aditya,
#   ritu, priya, neha, rahul, pooja, rohan, simran, kavya, amit, dev,
#   ishita, shreya, ratan, varun, manan, sumit, roopa, kabir, aayan,
#   shubh, ashutosh, advait, anand, tanya, tarun, sunny, mani, gokul,
#   vijay, shruti, suhani, mohit, kavitha, rehan, soham, rupali
_TONE_TO_SPEAKER = {
    "energetic":     "anushka",
    "calm":          "vidya",
    "authoritative": "karun",
    "friendly":      "manisha",
    "warm":          "vidya",
    "natural":       "vidya",
}
_DEFAULT_SPEAKER = "vidya"


def _default_speaker(language: str, tone: str) -> str:
    override = os.environ.get("SARVAM_DEFAULT_SPEAKER")
    if override:
        return override
    return _TONE_TO_SPEAKER.get((tone or "").lower(), _DEFAULT_SPEAKER)


def _pace_for_tone(tone: str) -> float:
    return {"energetic": 1.1, "calm": 0.9, "authoritative": 0.95, "friendly": 1.0}.get(tone, 1.0)


def _estimate_duration(text: str) -> float:
    # ~2.5 words per second.
    words = max(1, len(text.split()))
    return min(15.0, max(1.0, words / 2.5))


def _write_silence(out: Path, seconds: float) -> None:
    """Emit a tiny silent WAV at 22.05 kHz mono 16-bit PCM."""
    import struct
    import wave

    sample_rate = 22050
    n_samples = int(seconds * sample_rate)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"".join(struct.pack("<h", 0) for _ in range(n_samples)))
