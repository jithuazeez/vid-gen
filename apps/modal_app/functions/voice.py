"""Sarvam Bulbul-v2 multilingual TTS (per-scene, per-language).

Calls Sarvam Translate first when the source language differs from the
target. Pure HTTP — no GPU.
"""
from __future__ import annotations

from .. import storage as st
from ..providers import sarvam
from . import _common as cc

TTS_MODEL = "bulbul:v2"


def run(project_id: str, scene_id: str, language: str) -> dict:
    scene = cc.fetch_scene(scene_id)
    if scene is None:
        raise RuntimeError(
            f"Scene {scene_id!r} not found in the database Modal is connected to. "
            "Ensure the Modal 'database-url' secret points to the same PostgreSQL instance "
            "as the API and Celery worker, and that migrations are applied."
        )
    source_lang = scene.get("primary_language") or "en"
    script = scene.get("narration_script") or ""
    tone = (scene.get("brief") or {}).get("narration_tone", "calm")

    text = sarvam.translate(script, source_lang=source_lang, target_lang=language)

    h = st.content_hash({
        "scene_id": scene_id, "language": language, "text": text,
        "tone": tone, "model": TTS_MODEL,
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "voice", "scene_id": scene_id,
                    "language": language, "percent": 100, "cache_hit": True})
        return cached

    wav_path = sarvam.synthesize_speech(text, language, tone=tone)
    key = st.asset_key(project_id=project_id, asset_type="voice",
                       short_hash=h[:8], extension="wav",
                       scene_index=scene_id, language=language)
    bytes_ = st.upload_file(wav_path, key, "audio/wav")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="voice", language=language,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="audio/wav",
        metadata={"model": TTS_MODEL, "tone": tone, "translated_from": source_lang},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "voice", "scene_id": scene_id,
                "language": language, "percent": 100,
                "asset_id": record.get("asset_id")})
    return record
