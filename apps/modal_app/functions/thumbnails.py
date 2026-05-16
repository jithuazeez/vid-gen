"""SDXL-Turbo thumbnails — cheap preview gate for storyboard."""
from __future__ import annotations

from .. import storage as st
from . import _common as cc

MODEL_ID = "stabilityai/sdxl-turbo"


_THUMB_DIMS = {
    "16:9": (1024, 576),
    "9:16": (576, 1024),
    "1:1":  (768, 768),
    "4:5":  (640, 800),
    "5:4":  (800, 640),
    "21:9": (1024, 440),
}


def run(project_id: str, scene_id: str, prompt: str, seed: int = 42) -> dict:
    scene = cc.fetch_scene(scene_id)
    if scene is None:
        raise RuntimeError(
            f"Scene {scene_id!r} not found in the database Modal is connected to. "
            "Ensure the Modal 'database-url' secret points to the same PostgreSQL instance "
            "as the API and Celery worker, and that migrations are applied."
        )
    aspect = (scene.get("aspect_ratio") or "16:9").strip()
    width, height = _THUMB_DIMS.get(aspect, (1024, 576))

    h = st.content_hash({
        "prompt": prompt, "kind": "thumbnail",
        "model": MODEL_ID, "seed": int(seed),
        "width": width, "height": height,
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "thumbnail", "scene_id": scene_id, "percent": 100, "cache_hit": True})
        return cached

    from ..models import sdxl

    local = sdxl.generate(prompt, width=width, height=height, seed=seed)
    key = st.asset_key(project_id=project_id, asset_type="thumbnail",
                       short_hash=h[:8], extension="jpg",
                       scene_index=scene_id)
    bytes_ = st.upload_file(local, key, "image/jpeg")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="thumbnail", language=None,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="image/jpeg",
        metadata={"model": MODEL_ID},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "thumbnail", "scene_id": scene_id, "percent": 100,
                "asset_id": record.get("asset_id"), "storage_key": key})
    return record
