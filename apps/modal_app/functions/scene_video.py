"""LTX-Video I2V — silent scene videos, language-agnostic and cached."""
from __future__ import annotations

import os

from .. import storage as st
from . import _common as cc

MODEL_REVISION = "ltxv-13b-0.9.7-distilled-fp8"


def run(project_id: str, scene_id: str) -> dict:
    scene = cc.fetch_scene(scene_id)
    if scene is None:
        raise RuntimeError(
            f"Scene {scene_id!r} not found in the database Modal is connected to. "
            "Ensure the Modal 'database-url' secret points to the same PostgreSQL instance "
            "as the API and Celery worker, and that migrations are applied."
        )
    seed = int(scene.get("seed") or 42)
    duration = float(scene.get("duration_seconds") or 6.0)

    # Architecture.md §6: include character_ref_hashes so re-rolling a
    # character invalidates dependent scene videos.
    project_id_for_refs = str(scene.get("project_id") or project_id)
    char_ref_hashes = cc.fetch_character_ref_hashes(project_id_for_refs)

    h = st.content_hash({
        "scene_id": scene_id,
        "visual_prompt": scene.get("visual_prompt", ""),
        "character_ref_hashes": char_ref_hashes,
        "duration_s": duration,
        "model": MODEL_REVISION,
        "seed": seed,
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "scene_video", "scene_id": scene_id,
                    "percent": 100, "cache_hit": True})
        return cached

    # Conditioning image: prefer a character ref, fall back to a thumbnail.
    cond_key = None
    char_ref = cc.fetch_asset_by_type(
        project_id=str(scene.get("project_id") or project_id),
        scene_id=None, asset_type="character_ref", language=None,
    )
    if char_ref:
        cond_key = char_ref["storage_key"]
    else:
        thumb = cc.fetch_asset_by_type(
            project_id=str(scene.get("project_id") or project_id),
            scene_id=scene_id, asset_type="thumbnail", language=None,
        )
        if thumb:
            cond_key = thumb["storage_key"]

    cond_path = cc.download_to_tmp(cond_key) if cond_key else None

    from ..models import ltx

    local = ltx.run_i2v(
        prompt=scene.get("visual_prompt", ""),
        conditioning_image_path=cond_path,
        duration_s=duration,
        seed=seed,
    )
    key = st.asset_key(project_id=project_id, asset_type="scene_video",
                       short_hash=h[:8], extension="mp4",
                       scene_index=scene_id)
    bytes_ = st.upload_file(local, key, "video/mp4")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="scene_video", language=None,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="video/mp4",
        metadata={"model": MODEL_REVISION, "duration_s": duration},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "scene_video", "scene_id": scene_id,
                "percent": 100, "asset_id": record.get("asset_id")})
    return record
