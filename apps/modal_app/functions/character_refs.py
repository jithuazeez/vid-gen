"""SDXL-Turbo character reference images — used as conditioning for LTX-Video."""
from __future__ import annotations

from .. import storage as st
from . import _common as cc

MODEL_ID = "stabilityai/sdxl-turbo"


def run(project_id: str, character_id: str, name: str, description: str, seed: int = 42) -> dict:
    h = st.content_hash({
        "character_id": character_id, "description": description,
        "model": MODEL_ID, "seed": int(seed),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "character_ref", "character_id": character_id,
                    "percent": 100, "cache_hit": True})
        return cached

    if cc.fetch_project(project_id) is None:
        raise RuntimeError(
            f"Project {project_id!r} not found in the database Modal is connected to. "
            "Ensure the Modal 'database-url' secret points to the same PostgreSQL instance "
            "as the API and Celery worker, and that migrations are applied."
        )

    from ..models import sdxl

    prompt = (
        f"Cinematic portrait of {name}: {description}. "
        f"Three-quarter view, soft natural light, neutral background, "
        f"detailed face, photorealistic, 50mm lens, shallow depth of field."
    )
    local = sdxl.generate(prompt, width=768, height=768, seed=seed)
    key = st.asset_key(project_id=project_id, asset_type="character_ref",
                       short_hash=h[:8], extension="jpg",
                       character_id=character_id)
    bytes_ = st.upload_file(local, key, "image/jpeg")
    record = st.register_asset(
        project_id=project_id, scene_id=None,
        asset_type="character_ref", language=None,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="image/jpeg",
        metadata={"model": MODEL_ID, "character_id": character_id},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "character_ref", "character_id": character_id,
                "percent": 100, "asset_id": record.get("asset_id")})
    return record
