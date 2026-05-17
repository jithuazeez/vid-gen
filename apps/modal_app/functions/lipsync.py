"""Lip-sync — per scene, per language. Gated by `scene.has_speaker`.

Backend is LatentSync (see ``apps/modal_app/models/musetalk.py`` — name
kept for callsite stability). If the scene has no speaker we return None
without spinning the GPU model. The DAG is unchanged either way
(composite_scene checks for the asset and falls back to the silent
scene_video on miss).
"""
from __future__ import annotations

from .. import storage as st
from . import _common as cc

# Cache key — bump when the lip-sync model or its inference defaults
# change in a way that should invalidate previously rendered clips.
MODEL = "latentsync-1.6-stage2"


def run(project_id: str, scene_id: str, language: str) -> dict | None:
    scene = cc.fetch_scene(scene_id)
    if scene is None:
        raise RuntimeError(
            f"Scene {scene_id!r} not found in the database Modal is connected to. "
            "Ensure the Modal 'database-url' secret points to the same PostgreSQL instance "
            "as the API and Celery worker, and that migrations are applied."
        )
    if not scene.get("has_speaker"):
        return None

    h = st.content_hash({
        "scene_id": scene_id, "language": language, "model": MODEL,
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "lipsync_video", "scene_id": scene_id,
                    "language": language, "percent": 100, "cache_hit": True})
        return cached

    scene_video = cc.fetch_asset_by_type(
        project_id=project_id, scene_id=scene_id,
        asset_type="scene_video", language=None,
    )
    voice = cc.fetch_asset_by_type(
        project_id=project_id, scene_id=scene_id,
        asset_type="voice", language=language,
    )
    if not scene_video or not voice:
        return None

    sv_path = cc.download_to_tmp(scene_video["storage_key"])
    voice_path = cc.download_to_tmp(voice["storage_key"])

    from ..models import musetalk

    local = musetalk.sync(sv_path, voice_path)
    key = st.asset_key(project_id=project_id, asset_type="lipsync_video",
                       short_hash=h[:8], extension="mp4",
                       scene_index=scene_id, language=language)
    bytes_ = st.upload_file(local, key, "video/mp4")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="lipsync_video", language=language,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="video/mp4",
        metadata={"model": MODEL},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "lipsync_video", "scene_id": scene_id,
                "language": language, "percent": 100,
                "asset_id": record.get("asset_id")})
    return record
