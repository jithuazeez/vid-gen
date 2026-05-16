"""LTX-2 I2V — silent visuals + optional native audio.

Dual conditioning: the per-scene SDXL thumbnail anchors composition at the
opening latent frame, the project-wide character_ref hints identity at a
mid-latent index. Either may be missing; at least one must be present.

When the scene has no on-camera speaker we keep the audio track LTX-2 emits
alongside the video (registered as ``native_audio``). Speaker scenes get a
separate TTS narration + MuseTalk lip-sync, so we skip persisting the
model's audio for them.
"""
from __future__ import annotations

import os

from .. import storage as st
from . import _common as cc

MODEL_REVISION = "ltx-2-19b-stage1-cond-v1"


def _dims_for_aspect(aspect: str | None) -> tuple[int, int]:
    """Return (width, height) for an aspect ratio, both multiples of 32."""
    a = (aspect or "16:9").strip()
    table = {
        "16:9": (768, 448),
        "9:16": (448, 768),
        "1:1":  (576, 576),
        "4:5":  (512, 640),
        "5:4":  (640, 512),
        "21:9": (896, 384),
    }
    return table.get(a, (768, 448))


def _build_ltx_prompt(scene: dict, brief: dict) -> str:
    """Build the LTX-2 prompt.

    The thumbnail and character_ref conditions carry the spatial content of
    the shot, so the prompt describes the *action and motion happening
    during the clip* rather than redescribing the frame. Order: action +
    camera move first (the model weights leading tokens), storyboard
    visual second, narration's emotional context third, style trailer
    last.
    """
    visual = (scene.get("visual_prompt") or "").strip()
    narration = (scene.get("narration_script") or "").strip()
    style = (brief or {}).get("visual_style") or "cinematic"
    tone = (brief or {}).get("narration_tone") or "natural"
    duration = float(scene.get("duration_seconds") or 6.0)

    parts: list[str] = [
        f"A continuous {duration:.1f}-second cinematic shot. The camera "
        "moves with intent (slow dolly, gentle pan, or subtle push-in) "
        "while the subject performs a clear physical action.",
    ]
    if visual:
        parts.append(visual)
    if narration:
        snippet = narration.replace("\n", " ").strip()
        if len(snippet) > 200:
            snippet = snippet[:197].rsplit(" ", 1)[0] + "..."
        parts.append(
            "The on-screen action matches the emotional beat of the line: "
            f"\"{snippet}\"."
        )
    parts.append(
        f"Visual style: {style}. Mood: {tone}. Motivated lighting, "
        "shallow depth of field, 35mm-equivalent lens look, photoreal "
        "textures, naturalistic colour grade."
    )
    return " ".join(parts).strip()


NEGATIVE_PROMPT = (
    "low quality, blurry, distorted, deformed, watermark, text, caption, "
    "subtitle, cropped subject, cut-off head, extra limbs, warped face, "
    "jittery motion, flicker, jpeg artifacts, oversaturated, washed out"
)


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
    brief = scene.get("brief") or {}
    prompt = _build_ltx_prompt(scene, brief)
    has_speaker = bool(scene.get("has_speaker"))

    project_id_for_refs = str(scene.get("project_id") or project_id)
    char_ref_hashes = cc.fetch_character_ref_hashes(project_id_for_refs)

    width, height = _dims_for_aspect(scene.get("aspect_ratio"))

    h = st.content_hash({
        "scene_id": scene_id,
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "character_ref_hashes": char_ref_hashes,
        "duration_s": duration,
        "width": width,
        "height": height,
        "model": MODEL_REVISION,
        "seed": seed,
        "has_speaker": has_speaker,
        "v": os.environ.get("CACHE_VERSION", "v3"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "scene_video", "scene_id": scene_id,
                    "percent": 100, "cache_hit": True})
        return cached

    # Dual conditioning: thumbnail anchors composition, character_ref hints
    # identity. We fetch both independently rather than picking one — the
    # `LTX2ConditionPipeline` accepts a list of `LTX2VideoCondition`.
    thumb = cc.fetch_asset_by_type(
        project_id=project_id_for_refs,
        scene_id=scene_id, asset_type="thumbnail", language=None,
    )
    char_ref = cc.fetch_asset_by_type(
        project_id=project_id_for_refs,
        scene_id=None, asset_type="character_ref", language=None,
    )
    thumb_path = cc.download_to_tmp(thumb["storage_key"]) if thumb else None
    charref_path = cc.download_to_tmp(char_ref["storage_key"]) if char_ref else None

    from ..models import ltx

    video_path, audio_path = ltx.run_i2v(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        thumbnail_path=thumb_path,
        character_ref_path=charref_path,
        duration_s=duration,
        width=width,
        height=height,
        seed=seed,
        want_audio=not has_speaker,
    )
    key = st.asset_key(project_id=project_id, asset_type="scene_video",
                       short_hash=h[:8], extension="mp4",
                       scene_index=scene_id)
    bytes_ = st.upload_file(video_path, key, "video/mp4")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="scene_video", language=None,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="video/mp4",
        metadata={"model": MODEL_REVISION, "duration_s": duration,
                  "has_speaker": has_speaker},
    )

    if audio_path is not None:
        # Cache key parallels scene_video so a re-roll invalidates both.
        ah = st.content_hash({
            "scene_id": scene_id,
            "scene_video_hash": h,
            "model": MODEL_REVISION,
            "kind": "native_audio",
        })
        akey = st.asset_key(project_id=project_id, asset_type="native_audio",
                            short_hash=ah[:8], extension="wav",
                            scene_index=scene_id)
        a_bytes = st.upload_file(audio_path, akey, "audio/wav")
        st.register_asset(
            project_id=project_id, scene_id=scene_id,
            asset_type="native_audio", language=None,
            storage_key=akey, content_hash_value=ah,
            bytes_=a_bytes, mime_type="audio/wav",
            metadata={"model": MODEL_REVISION, "duration_s": duration,
                      "source": "ltx-2"},
        )

    cc.publish(project_id, "asset_progress",
               {"asset_type": "scene_video", "scene_id": scene_id,
                "percent": 100, "asset_id": record.get("asset_id")})
    return record
