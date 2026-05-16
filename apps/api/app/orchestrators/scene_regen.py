"""Single-scene LLM rewrite with locked continuity.

Loads ``docs/prompts/scene_regen_system.md`` and fills the templated context
blocks ([PROJECT_SPEC], [LOCKED_CHARACTERS], [LOCKED_STYLE],
[NEIGHBORING_SCENES], [ACTIVE_SCENE]) before calling Gemini with structured
output. Persists the rewrite to the ``scenes`` table; the caller is
responsible for enqueueing the actual asset re-render.

Wired into:
  - apps/api/app/routes/chat.py     (regenerate_scene intent branch)
  - apps/api/app/routes/scenes.py   (POST /scenes/{id}/regenerate optional body)
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Asset, Character, Project, Scene

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROMPT_PATH = _REPO_ROOT / "docs" / "prompts" / "scene_regen_system.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


# ── Public API ─────────────────────────────────────────────────────────


async def regenerate(
    *,
    session: AsyncSession,
    project: Project,
    scene_index: int | None = None,
    scene_id: uuid.UUID | None = None,
    user_modifier: str,
) -> dict[str, Any] | None:
    """Rewrite a single scene's visual_prompt + narration_script in place.

    Exactly one of ``scene_index`` / ``scene_id`` must be provided. Returns
    ``None`` if the target scene cannot be found. Otherwise returns the
    parsed Gemini output with the new fields plus ``scene_id`` and
    ``continuity_notes``.
    """
    active = await _load_active_scene(session, project.id, scene_index, scene_id)
    if active is None:
        return None

    prev_scene, next_scene = await _load_neighbors(session, project.id, active.scene_index)
    chars = await _load_characters(session, project.id)
    ref_uploads = await _load_reference_uploads(session, project.id)

    payload = _build_context_payload(
        project=project,
        active=active,
        prev_scene=prev_scene,
        next_scene=next_scene,
        characters=chars,
        reference_uploads=ref_uploads,
        user_modifier=user_modifier,
    )

    result = _gemini_regen(payload) or _fallback_regen(active, user_modifier)
    if result is None:
        return None

    # Persist the rewrite. Keep duration / has_speaker / character_ids unless
    # the LLM explicitly returned new values (the prompt instructs it not to).
    active.visual_prompt = result.get("visual_prompt") or active.visual_prompt
    active.narration_script = result.get("narration_script") or active.narration_script
    if "has_speaker" in result and isinstance(result["has_speaker"], bool):
        active.has_speaker = result["has_speaker"]
    await session.commit()
    await session.refresh(active)

    return {
        "scene_id": active.id,
        "scene_index": active.scene_index,
        "visual_prompt": active.visual_prompt,
        "narration_script": active.narration_script,
        "has_speaker": active.has_speaker,
        "continuity_notes": result.get("continuity_notes") or "",
    }


# ── DB helpers ─────────────────────────────────────────────────────────


async def _load_active_scene(
    session: AsyncSession,
    project_id: uuid.UUID,
    scene_index: int | None,
    scene_id: uuid.UUID | None,
) -> Scene | None:
    stmt = select(Scene).where(Scene.project_id == project_id)
    if scene_id is not None:
        stmt = stmt.where(Scene.id == scene_id)
    elif scene_index is not None:
        stmt = stmt.where(Scene.scene_index == int(scene_index))
    else:
        return None
    res = await session.execute(stmt.limit(1))
    return res.scalar_one_or_none()


async def _load_neighbors(
    session: AsyncSession, project_id: uuid.UUID, idx: int,
) -> tuple[Scene | None, Scene | None]:
    res = await session.execute(
        select(Scene)
        .where(Scene.project_id == project_id)
        .where(Scene.scene_index.in_([idx - 1, idx + 1]))
    )
    by_idx = {s.scene_index: s for s in res.scalars().all()}
    return by_idx.get(idx - 1), by_idx.get(idx + 1)


async def _load_characters(
    session: AsyncSession, project_id: uuid.UUID,
) -> list[Character]:
    res = await session.execute(
        select(Character).where(Character.project_id == project_id)
    )
    return list(res.scalars().all())


_REFERENCE_UPLOAD_TYPES = (
    "character_ref_upload", "style_ref_upload", "environment_ref_upload",
)


async def _load_reference_uploads(
    session: AsyncSession, project_id: uuid.UUID,
) -> list[Asset]:
    """All user-uploaded reference assets for this project (any kind).

    The descriptors live on each asset's ``asset_metadata['descriptors']``;
    see :mod:`app.orchestrators.reference_ingest` and the ``references``
    route.
    """
    res = await session.execute(
        select(Asset)
        .where(Asset.project_id == project_id)
        .where(Asset.asset_type.in_(_REFERENCE_UPLOAD_TYPES))
        .order_by(Asset.created_at.desc())
    )
    return list(res.scalars().all())


def _character_descriptors_by_name(uploads: list[Asset]) -> dict[str, dict[str, Any]]:
    """Map character_name → most recent valid descriptor for that character."""
    out: dict[str, dict[str, Any]] = {}
    for a in uploads:
        if a.asset_type != "character_ref_upload":
            continue
        meta = a.asset_metadata or {}
        name = (meta.get("character_name") or "").strip()
        descriptors = meta.get("descriptors")
        if not name or not isinstance(descriptors, dict):
            continue
        if "error" in descriptors:
            continue
        out.setdefault(name, descriptors)  # first wins; uploads are DESC by created_at
    return out


def _merged_style_descriptors(uploads: list[Asset]) -> dict[str, Any]:
    """Merge style + environment reference descriptors into a flat overlay
    for the [LOCKED_STYLE] block. Newest wins on conflict."""
    out: dict[str, Any] = {}
    for a in reversed(uploads):  # oldest first → newest overwrites
        if a.asset_type not in {"style_ref_upload", "environment_ref_upload"}:
            continue
        d = (a.asset_metadata or {}).get("descriptors") or {}
        if not isinstance(d, dict) or "error" in d:
            continue
        for k in ("color_palette", "lighting_style", "mood",
                  "location_type", "key_elements", "time_of_day", "weather"):
            if d.get(k) is not None:
                out[k] = d[k]
    return out


# ── Prompt context assembly ────────────────────────────────────────────


def _build_context_payload(
    *,
    project: Project,
    active: Scene,
    prev_scene: Scene | None,
    next_scene: Scene | None,
    characters: list[Character],
    reference_uploads: list[Asset],
    user_modifier: str,
) -> dict[str, Any]:
    brief = dict(project.brief or {})
    char_id_to_name = {c.id: c.name for c in characters}
    active_char_names = [
        char_id_to_name[cid] for cid in (active.character_ids or []) if cid in char_id_to_name
    ]

    char_descriptors = _character_descriptors_by_name(reference_uploads)
    style_overlay = _merged_style_descriptors(reference_uploads)

    return {
        "project_spec": {
            "video_type":            brief.get("video_type"),
            "visual_style":          brief.get("visual_style"),
            "duration_seconds":      float(project.duration_seconds) if project.duration_seconds else None,
            "primary_language":      project.primary_language,
            "narration_tone":        brief.get("narration_tone"),
            "aspect_ratio":          project.aspect_ratio,
            "subtitles_enabled":     brief.get("subtitles_enabled"),
            "subtitle_language":     brief.get("subtitle_language"),
            "text_overlays_enabled": brief.get("text_overlays_enabled"),
            "overlay_description":   brief.get("overlay_description"),
            "topic":                 brief.get("topic"),
        },
        "locked_characters": [
            {
                "name": c.name,
                "description": c.description,
                "reference_descriptors": char_descriptors.get(c.name),
            }
            for c in characters if c.name in active_char_names
        ],
        "locked_style": {
            "color_palette":  style_overlay.get("color_palette")  or brief.get("color_palette"),
            "lighting_style": style_overlay.get("lighting_style") or brief.get("lighting_style"),
            "mood":           style_overlay.get("mood")           or brief.get("mood"),
            **{k: v for k, v in style_overlay.items()
               if k in ("location_type", "key_elements", "time_of_day", "weather")},
        },
        "neighboring_scenes": {
            "prev_scene": _neighbor_summary(prev_scene),
            "next_scene": _neighbor_summary(next_scene),
        },
        "active_scene": {
            "scene_index":              active.scene_index,
            "duration_seconds":         float(active.duration_seconds),
            "current_visual_prompt":    active.visual_prompt,
            "current_narration_script": active.narration_script,
            "has_speaker":              active.has_speaker,
            "character_names":          active_char_names,
            "user_modifier":            user_modifier,
        },
    }


def _neighbor_summary(scene: Scene | None) -> dict[str, Any] | None:
    if scene is None:
        return None
    visual = (scene.visual_prompt or "").strip()
    narration = (scene.narration_script or "").strip()
    return {
        "scene_index":       scene.scene_index,
        "closing_visual":    _last_sentence(visual),
        "closing_narration": _last_clause(narration),
        "opening_visual":    _first_sentence(visual),
        "opening_narration": _first_clause(narration),
    }


def _first_sentence(s: str) -> str:
    for sep in (". ", "! ", "? "):
        if sep in s:
            return s.split(sep, 1)[0] + sep.strip()
    return s[:200]


def _last_sentence(s: str) -> str:
    parts = [p for p in s.replace("!", ".").replace("?", ".").split(".") if p.strip()]
    return (parts[-1].strip() if parts else s)[:200]


def _first_clause(s: str) -> str:
    for sep in (", ", "; ", ". "):
        if sep in s:
            return s.split(sep, 1)[0]
    return s[:120]


def _last_clause(s: str) -> str:
    parts = [p for p in s.replace(";", ",").split(",") if p.strip()]
    return (parts[-1].strip() if parts else s)[:120]


# ── Gemini call ────────────────────────────────────────────────────────


def _gemini_regen(payload: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.environ.get("GEMINI_API_KEY") or ""
    if not api_key or not SYSTEM_PROMPT:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            required=["scene_index", "visual_prompt", "narration_script"],
            properties={
                "scene_index":      types.Schema(type=types.Type.INTEGER),
                "duration_seconds": types.Schema(type=types.Type.NUMBER),
                "visual_prompt":    types.Schema(type=types.Type.STRING),
                "narration_script": types.Schema(type=types.Type.STRING),
                "has_speaker":      types.Schema(type=types.Type.BOOLEAN),
                "character_names":  types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "continuity_notes": types.Schema(type=types.Type.STRING),
            },
        )
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[json.dumps(payload, default=str)],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.55,
            ),
        )
        data = json.loads(resp.text or "{}")
        return data if isinstance(data, dict) and data.get("visual_prompt") else None
    except Exception:
        return None


def _fallback_regen(active: Scene, user_modifier: str) -> dict[str, Any]:
    """When no Gemini key is set, append the modifier and keep narration."""
    tagged_prompt = f"{active.visual_prompt}\n\nUser modifier: {user_modifier}"
    return {
        "scene_index":      active.scene_index,
        "duration_seconds": float(active.duration_seconds),
        "visual_prompt":    tagged_prompt,
        "narration_script": active.narration_script,
        "has_speaker":      active.has_speaker,
        "character_names":  [],
        "continuity_notes": "Stub regen: no Gemini key set; visual prompt appended.",
    }
