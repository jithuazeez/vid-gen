"""Background music — pluggable provider (ACE-Step 1.5 default, Magenta fallback).

One track per project, language-agnostic, reused across all language renders.
"""
from __future__ import annotations

import os

from .. import storage as st
from ..providers import MusicProvider
from . import _common as cc


def _provider() -> MusicProvider:
    name = os.environ.get("MUSIC_PROVIDER", "acestep").lower()
    if name == "magenta":
        from ..providers.magenta import MagentaProvider

        return MagentaProvider()
    from ..providers.acestep import AceStepProvider

    return AceStepProvider()


def run(project_id: str) -> dict | None:
    project = cc.fetch_project(project_id) or {}
    brief = project.get("brief") or {}
    if brief.get("music_enabled") is False:
        return None
    duration = float(project.get("duration_seconds") or 30)
    seed = int(project.get("seed") or 42)
    prompt = _music_prompt(brief)
    prov = _provider()

    h = st.content_hash({
        "prompt": prompt, "duration_s": duration,
        "provider": prov.name, "revision": prov.revision, "seed": seed,
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "music", "percent": 100, "cache_hit": True})
        return cached

    local = prov.synthesize(prompt, duration, seed=seed)
    key = st.asset_key(project_id=project_id, asset_type="music",
                       short_hash=h[:8], extension="mp3")
    bytes_ = st.upload_file(local, key, "audio/mpeg")
    record = st.register_asset(
        project_id=project_id, scene_id=None,
        asset_type="music", language=None,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="audio/mpeg",
        metadata={"provider": prov.name, "revision": prov.revision,
                  "prompt": prompt, "duration_s": duration},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "music", "percent": 100,
                "asset_id": record.get("asset_id")})
    return record


def _music_prompt(brief: dict) -> str:
    style = brief.get("visual_style", "cinematic")
    tone = brief.get("narration_tone", "calm")
    video_type = brief.get("video_type", "video")
    return (
        f"Instrumental background music for a {video_type}. "
        f"Style: {style}. Mood: {tone}. No vocals. Loopable."
    )
