"""Sarvam Bulbul-v2 multilingual TTS (per-scene, per-language).

Calls Sarvam Translate first when the source language differs from the
target. Pure HTTP — no GPU.
"""
from __future__ import annotations

import os
import re

from .. import storage as st
from ..providers import sarvam
from . import _audio, _common as cc

TTS_MODEL = "bulbul:v2"


# ── Speaker-label stripping ────────────────────────────────────────────
#
# The script writer often emits screenplay-style narration like
#   "ALICE: We were lost in the dark."
#   "Narrator (warm): Once upon a time..."
#   "[BOB] Wait — listen."
# The TTS engine reads everything verbatim, so without this scrub the
# audio (and the Whisper-derived subtitles) start each line with the
# character's name. Strip the label, leave the spoken line.

_LEADING_LABEL_RE = re.compile(
    r"""^\s*
        (?:
            \[[^\]]{1,40}\]            # [ALICE]
          | \([^)]{1,40}\)             # (Narrator)
          | [A-Z][A-Za-z0-9 .'\-]{0,30}(?:\s*\([^)]{1,30}\))?   # ALICE  /  Narrator (warm)
        )
        \s*[:—\-]\s+               # colon, em-dash, or hyphen separator
    """,
    re.VERBOSE,
)
_STAGE_DIR_RE = re.compile(r"\((?:[^)]{1,60})\)")          # (smiling) (V.O.)
_BRACKET_DIR_RE = re.compile(r"\[(?:[^\]]{1,60})\]")       # [pause] [SFX]
_WS_RE = re.compile(r"\s+")


def clean_for_tts(text: str) -> str:
    """Remove screenplay speaker labels and parenthetical stage directions.

    Applied per line so multi-line scripts keep their cadence. Conservative:
    only strips a leading label when followed by a colon/dash separator,
    so an in-sentence proper noun ("Alice walked in") is preserved.
    """
    if not text:
        return ""
    cleaned_lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            cleaned_lines.append("")
            continue
        # Repeatedly strip nested labels like "NARRATOR (V.O.): Alice: hi"
        for _ in range(3):
            new = _LEADING_LABEL_RE.sub("", line)
            if new == line:
                break
            line = new
        line = _STAGE_DIR_RE.sub("", line)
        line = _BRACKET_DIR_RE.sub("", line)
        line = _WS_RE.sub(" ", line).strip(" \t,;-—")
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def run(project_id: str, scene_id: str, language: str) -> dict:
    scene = cc.fetch_scene(scene_id)
    if scene is None:
        raise RuntimeError(
            f"Scene {scene_id!r} not found in the database Modal is connected to. "
            "Ensure the Modal 'database-url' secret points to the same PostgreSQL instance "
            "as the API and Celery worker, and that migrations are applied."
        )
    source_lang = scene.get("primary_language") or "en"
    raw_script = scene.get("narration_script") or ""
    script = clean_for_tts(raw_script)
    tone = (scene.get("brief") or {}).get("narration_tone", "calm")
    scene_duration_s = float(scene.get("duration_seconds") or 0.0)

    text = sarvam.translate(script, source_lang=source_lang, target_lang=language)

    h = st.content_hash({
        "scene_id": scene_id, "language": language, "text": text,
        "tone": tone, "model": TTS_MODEL,
        "duration_s": scene_duration_s,
        # Bumped when scene-length audio alignment landed.
        "v": os.environ.get("CACHE_VERSION", "v4"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "voice", "scene_id": scene_id,
                    "language": language, "percent": 100, "cache_hit": True})
        return cached

    wav_path = sarvam.synthesize_speech(text, language, tone=tone)
    align_meta: dict = {"action": "skip"}
    if scene_duration_s > 0:
        wav_path, align_meta = _audio.align_to_duration(str(wav_path), scene_duration_s)
    key = st.asset_key(project_id=project_id, asset_type="voice",
                       short_hash=h[:8], extension="wav",
                       scene_index=scene_id, language=language)
    bytes_ = st.upload_file(wav_path, key, "audio/wav")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="voice", language=language,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="audio/wav",
        metadata={"model": TTS_MODEL, "tone": tone, "translated_from": source_lang,
                  "alignment": align_meta},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "voice", "scene_id": scene_id,
                "language": language, "percent": 100,
                "asset_id": record.get("asset_id")})
    return record
