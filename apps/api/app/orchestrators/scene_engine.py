"""Scene Engine — two-stage Gemini planner → Timeline.

Stage 1 (script_writer): brief → narrative script with cast + spoken lines per beat.
Stage 2 (shot_planner):  brief + script → per-scene visual_prompt + tightened
                         character descriptions for SDXL.

The two-stage split keeps narration (what humans say) cleanly separated from
shot direction (what the camera sees). The TTS engine consumes the script's
narration verbatim, so it must never contain shot language.

Falls back to a deterministic canned plan when no Gemini key is set.

System prompts:
  - docs/prompts/script_writer_system.md
  - docs/prompts/shot_planner_system.md
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.schemas.timeline import CharacterPlan, ScenePlan, Timeline

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROMPTS_DIR = _REPO_ROOT / "docs" / "prompts"


def _load_prompt(name: str, default: str) -> str:
    p = _PROMPTS_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else default


SCRIPT_WRITER_PROMPT = _load_prompt(
    "script_writer_system.md",
    "You are a screenwriter for short-form video. Output JSON: "
    "{title, logline, cast: [...], beats: [{scene_index, duration_seconds, "
    "emotion, action, narration_script, has_speaker, speaker_name}]}.",
)
SHOT_PLANNER_PROMPT = _load_prompt(
    "shot_planner_system.md",
    "You are a director of photography. Given a script, output per-scene "
    "visual_prompts. Copy narration_script verbatim. Output JSON: "
    "{scenes: [...], characters: [...]}.",
)


# ── Public API ─────────────────────────────────────────────────────────


def plan(
    brief: dict[str, Any],
    references: dict[str, list[dict[str, Any]]] | None = None,
) -> Timeline:
    """Run the two-stage planner.

    ``references`` (optional) is the per-kind list of uploaded reference
    descriptors collected during the chat-driven brief. Shape::

        {
          "characters":  [ { "asset_id", "name", "descriptors": {...} }, ... ],
          "style":       [ {...} ],
          "environment": [ {...} ],
        }

    When present, the script writer is told to base its cast on these
    references (re-using ``name`` where supplied) and the shot planner
    bakes the style/environment descriptors into ``visual_prompt``.
    """
    refs = references or {}
    raw = _gemini_two_stage(brief, refs) or _fallback_plan(brief)
    scenes = [ScenePlan(**_normalize_scene(s)) for s in raw["scenes"]]
    chars = [CharacterPlan(**c) for c in raw.get("characters", [])]
    return Timeline(
        primary_language=brief.get("primary_language") or "en",
        scenes=scenes,
        characters=chars,
    )


# ── Normalisation ──────────────────────────────────────────────────────


_VALID_SUBTITLE_POSITIONS = {"auto", "top", "bottom", "custom"}
_SUBTITLE_POSITION_MAP = {
    "center": "auto", "middle": "auto", "none": "auto",
    "upper": "top", "above": "top",
    "lower": "bottom", "below": "bottom", "beneath": "bottom",
}


def _normalize_scene(s: dict[str, Any]) -> dict[str, Any]:
    raw_pos = s.get("subtitle_position") or "auto"
    subtitle_position = (
        raw_pos if raw_pos in _VALID_SUBTITLE_POSITIONS
        else _SUBTITLE_POSITION_MAP.get(str(raw_pos).lower(), "auto")
    )
    return {
        "scene_index": (
            s.get("scene_index") or s.get("scene_number") or s.get("index") or 1
        ),
        "duration_seconds": s.get("duration_seconds") or s.get("duration") or 5.0,
        "visual_prompt": (
            s.get("visual_prompt") or s.get("visual") or s.get("description")
            or s.get("prompt") or s.get("scene_description") or ""
        ),
        "narration_script": (
            s.get("narration_script") or s.get("narration") or s.get("script")
            or s.get("voiceover") or s.get("voice_over") or s.get("narrator_text") or ""
        ),
        # has_speaker is force-disabled while lip-sync is unimplemented.
        # See apps/modal_app/models/musetalk.py for the full story; once a
        # real lip-sync model is installed, revert this to
        # ``s.get("has_speaker", False)`` and re-enable the storyboard UI
        # toggle in apps/web/components/Storyboard/index.tsx.
        "has_speaker": False,
        "character_names": s.get("character_names") or [],
        "subtitle_position": subtitle_position,
    }


# ── Two-stage Gemini pipeline ─────────────────────────────────────────


def _gemini_two_stage(
    brief: dict[str, Any],
    references: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    api_key = os.environ.get("GEMINI_API_KEY") or ""
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        script = _gemini_script(client, types, brief, references)
        if not script or not script.get("beats"):
            return None

        shots = _gemini_shotlist(client, types, brief, script, references)
        if not shots or not shots.get("scenes"):
            return None

        return _merge_script_and_shots(script, shots)
    except Exception:
        return None


def _gemini_script(
    client, types, brief: dict[str, Any],
    references: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    cast_member_schema = types.Schema(
        type=types.Type.OBJECT,
        required=["name", "role", "description"],
        properties={
            "name":        types.Schema(type=types.Type.STRING),
            "role":        types.Schema(type=types.Type.STRING),
            "description": types.Schema(type=types.Type.STRING),
        },
    )
    beat_schema = types.Schema(
        type=types.Type.OBJECT,
        required=["scene_index", "duration_seconds", "emotion",
                  "action", "narration_script", "has_speaker"],
        properties={
            "scene_index":      types.Schema(type=types.Type.INTEGER),
            "duration_seconds": types.Schema(type=types.Type.NUMBER),
            "emotion":          types.Schema(type=types.Type.STRING),
            "action":           types.Schema(type=types.Type.STRING),
            "narration_script": types.Schema(type=types.Type.STRING),
            "has_speaker":      types.Schema(type=types.Type.BOOLEAN),
            "speaker_name":     types.Schema(type=types.Type.STRING),
        },
    )
    response_schema = types.Schema(
        type=types.Type.OBJECT,
        required=["title", "logline", "cast", "beats"],
        properties={
            "title":   types.Schema(type=types.Type.STRING),
            "logline": types.Schema(type=types.Type.STRING),
            "cast":    types.Schema(type=types.Type.ARRAY, items=cast_member_schema),
            "beats":   types.Schema(type=types.Type.ARRAY, items=beat_schema),
        },
    )
    payload = {"brief": brief, "references": references or {}}
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[json.dumps(payload, default=str)],
        config=types.GenerateContentConfig(
            system_instruction=SCRIPT_WRITER_PROMPT,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.85,  # higher = more creative narration
        ),
    )
    data = json.loads(resp.text or "{}")
    return data if isinstance(data, dict) and "beats" in data else None


def _gemini_shotlist(
    client, types, brief: dict[str, Any], script: dict[str, Any],
    references: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    scene_schema = types.Schema(
        type=types.Type.OBJECT,
        required=["scene_index", "duration_seconds", "visual_prompt",
                  "narration_script", "has_speaker"],
        properties={
            "scene_index":       types.Schema(type=types.Type.INTEGER),
            "duration_seconds":  types.Schema(type=types.Type.NUMBER),
            "visual_prompt":     types.Schema(type=types.Type.STRING),
            "narration_script":  types.Schema(type=types.Type.STRING),
            "has_speaker":       types.Schema(type=types.Type.BOOLEAN),
            "character_names":   types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
            ),
            "subtitle_position": types.Schema(
                type=types.Type.STRING,
                enum=["auto", "top", "bottom", "custom"],
            ),
        },
    )
    char_schema = types.Schema(
        type=types.Type.OBJECT,
        required=["name", "description"],
        properties={
            "name":        types.Schema(type=types.Type.STRING),
            "description": types.Schema(type=types.Type.STRING),
        },
    )
    response_schema = types.Schema(
        type=types.Type.OBJECT,
        required=["scenes", "characters"],
        properties={
            "scenes":     types.Schema(type=types.Type.ARRAY, items=scene_schema),
            "characters": types.Schema(type=types.Type.ARRAY, items=char_schema),
        },
    )
    payload = {"brief": brief, "script": script, "references": references or {}}
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[json.dumps(payload, default=str)],
        config=types.GenerateContentConfig(
            system_instruction=SHOT_PLANNER_PROMPT,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.45,  # lower = obedient to the script, less drift
        ),
    )
    data = json.loads(resp.text or "{}")
    return data if isinstance(data, dict) and "scenes" in data else None


def _merge_script_and_shots(
    script: dict[str, Any], shots: dict[str, Any]
) -> dict[str, Any]:
    """Combine stage-1 script + stage-2 shotlist into the legacy plan shape.

    Script is the source of truth for narration; shotlist for visuals. We
    align by scene_index. If the shotlist somehow rewrote a narration line
    (it was told not to), we restore the script's version.
    """
    beats_by_idx = {int(b["scene_index"]): b for b in script.get("beats", [])}
    scenes_out: list[dict[str, Any]] = []
    for s in shots.get("scenes", []):
        idx = int(s.get("scene_index") or 0)
        beat = beats_by_idx.get(idx, {})
        scenes_out.append({
            **s,
            "duration_seconds": beat.get("duration_seconds") or s.get("duration_seconds"),
            "narration_script": beat.get("narration_script") or s.get("narration_script"),
            # Force-disabled — see _normalize_scene above.
            "has_speaker": False,
        })
    return {"scenes": scenes_out, "characters": shots.get("characters", [])}


# ── Deterministic fallback (no Gemini key) ────────────────────────────


def _fallback_plan(brief: dict[str, Any]) -> dict[str, Any]:
    duration = int(brief.get("duration_seconds") or 30)
    has_chars = bool(brief.get("has_characters"))
    topic = (brief.get("topic") or "your story").strip() or "your story"
    style = brief.get("visual_style") or "cinematic"
    tone = brief.get("narration_tone") or "warm"

    n = max(3, min(6, duration // 6))
    per = round(duration / n, 2)

    beats = [
        ("Establishing shot", "Wide cinematic establishing shot with soft natural light."),
        ("Detail close-up", "Macro shot, shallow depth of field, gentle slow motion."),
        ("Movement", "Mid shot in motion, hands in frame, golden hour."),
        ("Atmosphere", "B-roll of texture and mood, warm tone, subtle ambient sound."),
        ("Brand reveal", "Logo lock-up over textured background, slow zoom-out."),
        ("Closing wide", "Final wide shot, fade to brand mark."),
    ]
    scenes = []
    for i in range(n):
        _title, prompt = beats[i]
        scenes.append({
            "scene_index": i + 1,
            "duration_seconds": per,
            "visual_prompt": (
                f"{prompt} Subject of the video: {topic}. Style: {style}. "
                "Camera: shoulder height. Lighting: cinematic, soft fill."
            ),
            "narration_script": _narration_for(i, n, topic, tone),
            # Force-disabled while lip-sync is unimplemented. See
            # apps/modal_app/models/musetalk.py.
            "has_speaker": False,
            "subtitle_position": "auto",
        })

    chars: list[dict[str, Any]] = []
    if has_chars:
        chars.append({
            "name": "Presenter",
            "description": (
                "Friendly mid-20s presenter, neutral background, warm smile, "
                "natural lighting, eye contact with the camera."
            ),
        })
    return {"scenes": scenes, "characters": chars}


def _narration_for(i: int, n: int, topic: str, tone: str) -> str:
    intros = [f"This is the story of {topic}.",
              f"From the very first moment, {topic} feels different."]
    middles = ["Crafted from care, refined with intent.",
               "Every detail, considered.",
               "Made for moments that matter."]
    closes = [f"{topic.title()} — made for you.", "The long way, every time."]
    if i == 0:
        return intros[0]
    if i == n - 1:
        return closes[0]
    return middles[(i - 1) % len(middles)]
