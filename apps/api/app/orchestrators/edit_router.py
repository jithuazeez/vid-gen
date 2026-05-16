"""LangGraph edit-router — Screens 2 + 4.

A compiled `StateGraph` with two nodes:

  classify ──▶ confirm  (terminal)

`classify` runs the LLM (Gemini 3.1 Flash-Lite) with structured output;
falls back to heuristics. `confirm` synthesizes the preview string and
flags low-confidence intents for clarification.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

_PROMPT_PATH = Path(__file__).resolve().parents[4] / "docs" / "prompts" / "edit_router_system.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


# Cached Gemini client — see conversation.py for the rationale.
_GEMINI_CLIENT = None


def _get_gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is not None:
        return _GEMINI_CLIENT
    api_key = os.environ.get("GEMINI_API_KEY") or ""
    if not api_key:
        return None
    try:
        from google import genai
        _GEMINI_CLIENT = genai.Client(api_key=api_key)
        return _GEMINI_CLIENT
    except Exception:
        return None

Intent = Literal[
    "edit_scene", "regenerate_scene", "edit_overlay",
    "change_language", "ask_question", "unknown",
]


@dataclass
class IntentResult:
    intent: Intent
    args: dict[str, Any]
    confidence: float
    preview: str
    candidates: list[Intent] = None  # type: ignore[assignment]

    def clarification_chips(self) -> list[str]:
        """Top-2 candidate intent labels, formatted for the chat chip row.

        Architecture.md §13: low-confidence (<0.6) intents should ask a
        clarifying question with chips suggesting the top candidates.
        """
        cands = self.candidates or [self.intent]
        labels = {
            "edit_scene":       "Edit a scene",
            "regenerate_scene": "Regenerate a scene",
            "edit_overlay":     "Edit an overlay",
            "change_language":  "Change language",
            "ask_question":     "Just asking",
            "unknown":          "Something else",
        }
        seen, out = set(), []
        for c in cands:
            label = labels.get(c, c)
            if label not in seen:
                out.append(label)
                seen.add(label)
            if len(out) >= 2:
                break
        return out


def classify(
    message: str, context: dict[str, Any] | None = None,
) -> IntentResult:
    """Classify a user chat message into an edit intent.

    ``context`` (optional) gives the LLM situational awareness of the
    current storyboard so it can resolve references like "the last scene"
    or "make Mira's scene happier". Recommended shape::

        {
          "scene_count": int,
          "scenes": [
            {"index": int, "summary": str, "has_speaker": bool,
             "character_names": [str]},
            ...
          ],
          "characters": [str],          # cast names
          "active_language": str,
          "primary_language": str,
        }
    """
    graph = _build_graph()
    state = graph.invoke({
        "message": message,
        "context": context or {},
        "intent": "unknown",
        "args": {},
        "confidence": 0.0,
        "preview": "",
        "candidates": [],
    })
    return IntentResult(
        intent=state["intent"],
        args=state["args"],
        confidence=state["confidence"],
        preview=state["preview"],
        candidates=state.get("candidates") or [state["intent"]],
    )


# ── Graph state ────────────────────────────────────────────────────────


class _State(TypedDict):
    message: str
    context: dict[str, Any]
    intent: Intent
    args: dict[str, Any]
    confidence: float
    preview: str
    candidates: list[Intent]


def _node_classify(state: _State) -> _State:
    ctx = state.get("context") or {}
    out = (
        _gemini_classify(state["message"], ctx)
        or _heuristic_classify(state["message"], ctx)
    )
    state.update(out)
    if not state.get("candidates"):
        # Always include the chosen intent first; add a second-best fallback
        # so the UI can offer a 2-chip clarification even without an LLM
        # confidence vector.
        fallback = "ask_question" if state["intent"] != "ask_question" else "edit_scene"
        state["candidates"] = [state["intent"], fallback]
    return state


def _node_confirm(state: _State) -> _State:
    if not state["preview"]:
        state["preview"] = _default_preview(state["intent"], state["args"])
    if state["confidence"] < 0.6 and state["intent"] != "ask_question":
        state["preview"] = (
            "Not sure I caught that — " + state["preview"]
            if state["preview"] else "Could you rephrase that?"
        )
    return state


def _build_graph():
    g = StateGraph(_State)
    g.add_node("classify", _node_classify)
    g.add_node("confirm", _node_confirm)
    g.add_edge(START, "classify")
    g.add_edge("classify", "confirm")
    g.add_edge("confirm", END)
    return g.compile()


# ── Heuristic fallback ─────────────────────────────────────────────────


_LANG_WORDS = {"english": "en", "hindi": "hi", "marathi": "mr", "tamil": "ta", "punjabi": "pa"}


def _heuristic_classify(message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    low = message.lower().strip()
    ctx = context or {}
    scene_count = int(ctx.get("scene_count") or 0)

    for word, code in _LANG_WORDS.items():
        if word in low:
            return {
                "intent": "change_language",
                "args": {"language": code},
                "confidence": 0.9,
                "preview": f"Switch to {word.title()} narration.",
            }

    # Resolve "last scene" / "final scene" / "first scene" using context.
    relative_idx: int | None = None
    if scene_count > 0:
        if re.search(r"\b(last|final|closing|ending)\s+scene\b", low):
            relative_idx = scene_count
        elif re.search(r"\b(first|opening|starting)\s+scene\b", low):
            relative_idx = 1

    m = re.search(r"\b(re-?gen(?:erate)?|redo|remake)\s+scene\s+(\d+)\b", low)
    if m:
        idx = int(m.group(2))
        return {
            "intent": "regenerate_scene",
            "args": {"scene_index": idx, "prompt_modifier": message},
            "confidence": 0.92,
            "preview": f"Regenerate scene {idx}.",
        }
    if relative_idx and re.search(r"\b(re-?gen(?:erate)?|redo|remake|try again|different take)\b", low):
        return {
            "intent": "regenerate_scene",
            "args": {"scene_index": relative_idx, "prompt_modifier": message},
            "confidence": 0.85,
            "preview": f"Regenerate scene {relative_idx}.",
        }

    m = re.search(r"\bscene\s+(\d+)\b", low)
    if m:
        idx = int(m.group(1))
        if scene_count and not (1 <= idx <= scene_count):
            return {
                "intent": "unknown",
                "args": {"raw": message, "scene_index": idx},
                "confidence": 0.0,
                "preview": f"You mentioned scene {idx}, but there are only {scene_count} scenes.",
            }
        field, value = _guess_field(message)
        return {
            "intent": "edit_scene",
            "args": {"scene_index": idx, "field": field, "value": value},
            "confidence": 0.7 if field else 0.45,
            "preview": (f"Edit scene {idx} ({field} → '{value}')." if field
                        else f"Edit something in scene {idx}."),
        }

    if relative_idx is not None:
        field, value = _guess_field(message)
        return {
            "intent": "edit_scene",
            "args": {"scene_index": relative_idx, "field": field, "value": value},
            "confidence": 0.65 if field else 0.4,
            "preview": (f"Edit scene {relative_idx} ({field} → '{value}')." if field
                        else f"Edit something in scene {relative_idx}."),
        }

    if any(k in low for k in ("overlay", "cta", "lower third", "call to action", "subscribe button")):
        return {
            "intent": "edit_overlay",
            "args": {"raw": message},
            "confidence": 0.55,
            "preview": "Edit an overlay on the timeline.",
        }

    if low.endswith("?") or any(low.startswith(w) for w in ("what", "why", "how", "when")):
        return {
            "intent": "ask_question",
            "args": {"text": message},
            "confidence": 0.6,
            "preview": "Q&A about your project.",
        }

    return {
        "intent": "unknown",
        "args": {"raw": message},
        "confidence": 0.0,
        "preview": "Sorry — can you rephrase that?",
    }


def _guess_field(message: str) -> tuple[str | None, str | None]:
    low = message.lower()
    if any(k in low for k in ("narration", "script", "voice over", "voiceover", "say")):
        return "narration_script", message
    if any(k in low for k in ("visual", "prompt", "shot", "look")):
        return "visual_prompt", message
    if "speaker" in low or "talking" in low or "on camera" in low:
        return "has_speaker", "True" if ("on" in low or "yes" in low) else "False"
    if "subtitle" in low and ("top" in low or "bottom" in low):
        return "subtitle_position", "top" if "top" in low else "bottom"
    return None, None


def _default_preview(intent: str, args: dict[str, Any]) -> str:
    if intent == "change_language":
        return f"Switch to language={args.get('language')}."
    if intent == "regenerate_scene":
        return f"Regenerate scene {args.get('scene_index')}."
    if intent == "edit_scene":
        return f"Edit scene {args.get('scene_index')} field {args.get('field')}."
    if intent == "edit_overlay":
        return "Edit overlay."
    if intent == "ask_question":
        return "Answer your question."
    return "Sorry — can you rephrase that?"


# ── Gemini classification ──────────────────────────────────────────────


_CLASSIFY_SYS = SYSTEM_PROMPT or (
    "Classify the user's message into one of: edit_scene, regenerate_scene, "
    "edit_overlay, change_language, ask_question, unknown. Return JSON: "
    "{intent, confidence, args, preview}."
)

_VALID_INTENTS = {"edit_scene", "regenerate_scene", "edit_overlay",
                  "change_language", "ask_question", "unknown"}


def _parse_classify_response(text: str | None) -> dict[str, Any] | None:
    try:
        data = json.loads(text or "{}")
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    intent = data.get("intent", "unknown")
    if intent not in _VALID_INTENTS:
        return None
    cands = data.get("candidates") or []
    if not isinstance(cands, list):
        cands = []
    cands = [c for c in cands if c in _VALID_INTENTS]
    return {
        "intent": intent,
        "args": data.get("args") or {},
        "confidence": float(data.get("confidence") or 0.5),
        "preview": str(data.get("preview") or ""),
        "candidates": cands,
    }


def _gemini_classify(
    message: str, context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    client = _get_gemini_client()
    if client is None:
        return None
    try:
        from google.genai import types

        payload = {"message": message, "context": context or {}}
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[json.dumps(payload, default=str)],
            config=types.GenerateContentConfig(
                system_instruction=_CLASSIFY_SYS,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return _parse_classify_response(resp.text)
    except Exception:
        return None


async def _gemini_classify_async(
    message: str, context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Async variant used by the SSE chat route — avoids burning a worker
    thread on a blocking Gemini call."""
    client = _get_gemini_client()
    if client is None:
        return None
    try:
        from google.genai import types

        payload = {"message": message, "context": context or {}}
        resp = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[json.dumps(payload, default=str)],
            config=types.GenerateContentConfig(
                system_instruction=_CLASSIFY_SYS,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return _parse_classify_response(resp.text)
    except Exception:
        return None


async def aclassify(
    message: str, context: dict[str, Any] | None = None,
) -> IntentResult:
    """Async classify — same contract as ``classify`` but uses Gemini's async
    API directly instead of `asyncio.to_thread(classify, ...)`."""
    ctx = context or {}
    out = (
        await _gemini_classify_async(message, ctx)
        or _heuristic_classify(message, ctx)
    )
    intent = out.get("intent", "unknown")
    cands = out.get("candidates") or []
    if not cands:
        fallback = "ask_question" if intent != "ask_question" else "edit_scene"
        cands = [intent, fallback]
    preview = out.get("preview") or _default_preview(intent, out.get("args") or {})
    confidence = float(out.get("confidence") or 0.0)
    if confidence < 0.6 and intent != "ask_question":
        preview = ("Not sure I caught that — " + preview
                   if preview else "Could you rephrase that?")
    return IntentResult(
        intent=intent,
        args=out.get("args") or {},
        confidence=confidence,
        preview=preview,
        candidates=cands,
    )
