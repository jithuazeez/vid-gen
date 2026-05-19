"""LTX-Video I2V — silent scene videos, language-agnostic and cached."""
from __future__ import annotations

import os

from .. import storage as st
from . import _common as cc

MODEL_REVISION = "ltxv-13b-0.9.7-distilled-fp8+motion-prompt-v2+runway-v1"

# Extra seconds of camera-motion runway appended to every non-final,
# non-explainer scene. Consumed by the xfade overlap in final_export so
# the visible scene length matches the scene's logical duration.
TRANSITION_RUNWAY_S = 1.0


def _dims_for_aspect(aspect: str | None) -> tuple[int, int]:
    """Return (width, height) for an aspect ratio, both multiples of 32.

    Sized for LTX 0.9.x: ~344k-pixel budget (the model's sweet spot per
    its model card). Higher resolutions cause noticeable detail loss
    and softer motion on the distilled checkpoint.
    """
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


def _build_ltx_prompt(scene: dict, brief: dict, *, has_runway: bool = False,
                      render_duration_s: float | None = None) -> str:
    """Build a motion-first LTX prompt.

    LTX 0.9.x is heavily weighted toward the leading tokens of the prompt
    and tends to produce near-still output ("animated photo") when the
    opening describes a static scene. The fix is to lead with explicit
    camera-move and subject-action language, then layer the storyboard
    description and style cues after. The narration line is appended as
    *emotional context*, not transcription — it tells the model what
    beat the shot is hitting without asking it to render text.
    """
    visual = (scene.get("visual_prompt") or "").strip()
    narration = (scene.get("narration_script") or "").strip()
    style = (brief or {}).get("visual_style") or "cinematic"
    tone = (brief or {}).get("narration_tone") or "natural"
    duration = float(render_duration_s if render_duration_s is not None
                     else (scene.get("duration_seconds") or 6.0))

    parts: list[str] = []

    # 1. Lead with motion — larger magnitude than before. LTX 0.9.x
    #    weights the leading tokens heavily, so this is where we earn
    #    visible camera movement. The previous "smoothly / gentle /
    #    subtle" wording produced near-still output.
    parts.append(
        f"A continuous {duration:.1f}-second cinematic shot with pronounced, "
        "clearly-visible camera motion: the camera executes a confident move "
        "— a bold dolly push-in, a wide arc around the subject, a fast "
        "tracking pan, or a crane rise — covering meaningful distance across "
        "the shot. Strong parallax. Foreground elements sweep past. The "
        "subject performs a clear physical action."
    )

    # 2. Storyboard description, restructured to put action verbs early
    #    where possible. We pass it through verbatim — the planner already
    #    wrote it for visual intent.
    if visual:
        parts.append(visual)

    # 3. Spoken-line context for emotional tone — wrapped so the model
    #    treats it as *what's happening underneath the dialogue*, not as
    #    text to render.
    if narration:
        snippet = narration.replace("\n", " ").strip()
        if len(snippet) > 200:
            snippet = snippet[:197].rsplit(" ", 1)[0] + "..."
        parts.append(
            f"The on-screen action matches the emotional beat of the line: "
            f"\"{snippet}\"."
        )

    # 4. Style trailer — motivated lighting, lens, mood. Trailing position
    #    is intentional: LTX uses these as conditioning hints, not as the
    #    primary directive.
    parts.append(
        f"Visual style: {style}. Mood: {tone}. Motivated lighting, "
        "shallow depth of field, 35mm-equivalent lens look, photoreal "
        "textures, naturalistic colour grade. Pronounced camera motion "
        "throughout — every second of the clip shows the framing changing. "
        "No freeze frames, no static stills."
    )

    if has_runway:
        # Last ~1s of the clip is consumed by an xfade overlap into the
        # next scene's opening. Telling LTX to ease into an outward move
        # gives the crossfade something cinematic to work with instead
        # of crossfading mid-action.
        parts.append(
            "The final beat of the shot eases into an outward motion — "
            "the camera drifts back, pans off, or pushes through — "
            "leaving the frame ready to cut cleanly to the next shot."
        )

    return " ".join(parts).strip()


def _build_explainer_prompt(scene: dict, brief: dict) -> str:
    """Build a locked-off, frontal LTX prompt for explainer mode.

    The presenter speaks direct-to-camera in a stable bust-framed shot.
    No camera movement, no head turning — every frame must contain a
    frontal face so the downstream LipSync / InsightFace pipeline
    detects reliably. The conditioning image (the SDXL character_ref,
    generated with frontal=True) already sets the framing; this prompt
    tells LTX to *hold* it.
    """
    duration = float(scene.get("duration_seconds") or 6.0)
    return (
        f"A locked-off {duration:.1f}-second medium bust shot of a "
        "presenter looking directly into the camera and speaking. "
        "Subtle natural facial expressions: small lip movements, "
        "occasional gentle blinks, minimal head micro-movement. "
        "Zero camera movement — stable tripod frame throughout. "
        "Neutral studio backdrop. Soft key light from camera-left, "
        "gentle fill from right. Photorealistic, broadcast newsreader "
        "composition. The presenter remains centered, head level, "
        "both eyes visible, face directly toward camera for the entire clip."
    )


# Negative prompt — explicit suppression of the failure modes we've
# actually seen in renders: still-photo output, distorted faces, baked-in
# captions, jitter. LTX 0.9.x respects negative prompts well.
NEGATIVE_PROMPT = (
    "still photo, static frame, frozen image, animated still, "
    "no motion, motionless subject, locked-off camera, tripod shot, "
    "static framing, minimal motion, barely perceptible movement, "
    "slow motion, "
    "low quality, blurry, distorted, deformed, watermark, text, caption, "
    "subtitle, cropped subject, cut-off head, extra limbs, warped face, "
    "jittery motion, flicker, jpeg artifacts, oversaturated, washed out"
)


# Explainer mode reverses several of the defaults: we *want* a near-still
# subject (presenter holds frame) and we explicitly reject any of the
# camera moves and angle changes that would break frontal face detection.
NEGATIVE_PROMPT_EXPLAINER = (
    "profile view, three-quarter view, side view, head turned, "
    "head turning away, looking away, head tilted, dutch tilt, "
    "hand near face, hand on chin, microphone in frame, "
    "dolly, pan, push-in, pull-back, zoom, handheld, camera shake, "
    "motion blur, cinematic angle, low angle, high angle, wide shot, "
    "environmental shot, multiple people, crowd, background motion, "
    "low quality, blurry, distorted, deformed, watermark, text, caption, "
    "subtitle, cropped subject, cut-off head, warped face, "
    "flicker, jpeg artifacts"
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
    is_explainer = (brief.get("video_type") == "explainer")

    # Non-final, non-explainer scenes get a transition-runway tail so the
    # final-export xfade has something to crossfade with. Explainer mode
    # keeps a locked-off frame for lipsync — no runway, no xfade.
    project_id_for_count = str(scene.get("project_id") or project_id)
    scene_idx = int(scene.get("scene_index") or 0)
    total_scenes = cc.fetch_scene_count(project_id_for_count)
    is_final_scene = (scene_idx >= total_scenes - 1) if total_scenes > 0 else True
    has_runway = (not is_explainer) and (not is_final_scene)
    render_duration = duration + (TRANSITION_RUNWAY_S if has_runway else 0.0)

    prompt = (
        _build_explainer_prompt(scene, brief)
        if is_explainer
        else _build_ltx_prompt(scene, brief, has_runway=has_runway,
                               render_duration_s=render_duration)
    )
    negative = NEGATIVE_PROMPT_EXPLAINER if is_explainer else NEGATIVE_PROMPT

    # Architecture.md §6: include character_ref_hashes so re-rolling a
    # character invalidates dependent scene videos.
    project_id_for_refs = str(scene.get("project_id") or project_id)
    char_ref_hashes = cc.fetch_character_ref_hashes(project_id_for_refs)

    width, height = _dims_for_aspect(scene.get("aspect_ratio"))

    h = st.content_hash({
        "scene_id": scene_id,
        "prompt": prompt,
        "negative_prompt": negative,
        "character_ref_hashes": char_ref_hashes,
        "duration_s": render_duration,
        "logical_duration_s": duration,
        "has_runway": has_runway,
        "width": width,
        "height": height,
        "model": MODEL_REVISION,
        "seed": seed,
        "explainer": is_explainer,
        "v": os.environ.get("CACHE_VERSION", "v3"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "scene_video", "scene_id": scene_id,
                    "percent": 100, "cache_hit": True})
        return cached

    # Conditioning image: prefer the per-scene thumbnail (SDXL render of
    # this scene's visual_prompt — captures the shot composition the
    # storyboard called for). Fall back to a project-wide character_ref
    # if the thumbnail step never ran. Using the thumbnail keeps shot
    # framing, set, lighting, and character placement consistent with
    # what the user reviewed on the storyboard.
    #
    # Explainer mode skips the thumbnail and always uses the frontal
    # character_ref — every scene must be the same locked-off bust shot
    # of the same presenter, and the per-scene thumbnails would pull each
    # scene toward a different composition.
    cond_key = None
    if is_explainer:
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
        else:
            char_ref = cc.fetch_asset_by_type(
                project_id=str(scene.get("project_id") or project_id),
                scene_id=None, asset_type="character_ref", language=None,
            )
            if char_ref:
                cond_key = char_ref["storage_key"]

    cond_path = cc.download_to_tmp(cond_key) if cond_key else None

    from ..models import ltx

    local = ltx.run_i2v(
        prompt=prompt,
        negative_prompt=negative,
        conditioning_image_path=cond_path,
        duration_s=render_duration,
        width=width,
        height=height,
        seed=seed,
        guidance_scale=4.5 if is_explainer else None,
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
        metadata={"model": MODEL_REVISION, "duration_s": render_duration,
                  "logical_duration_s": duration, "has_runway": has_runway},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "scene_video", "scene_id": scene_id,
                "percent": 100, "asset_id": record.get("asset_id")})
    return record
