"""LangGraph conversation orchestrator — collect mode (Screen 1).

Architecture.md §13. Two entry points share the same nodes:

* `step()`   — synchronous, blocking, used by tests and any non-SSE caller.
                Runs through a compiled `StateGraph`.
* `astream()` — async generator yielding (event, payload) tuples as the LLM
                streams tokens. Used by the chat SSE route so the UI can
                paint `thinking` → partial `slot_update` → `question` as
                they happen instead of waiting for the full Gemini call.

Falls back to deterministic heuristics when no Gemini key is set, so the
demo runs offline.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.schemas.brief import Brief

# Valid literal sets — used to sanitize LLM output before it touches Pydantic
_VALID_SLOT_VALUES: dict[str, set] = {
    "video_type":       {"explainer", "cinematic", "social_reel", "ad"},
    "visual_style":     {"realistic", "animated", "documentary", "minimalist"},
    "primary_language": {"en", "hi", "mr", "ta", "pa"},
    "narration_tone":   {"energetic", "calm", "authoritative", "friendly"},
    "aspect_ratio":     {"16:9", "9:16", "1:1"},
}

# Normalize full language names that Gemini sometimes returns instead of codes
_LANG_NORM: dict[str, str] = {
    "english": "en", "hindi": "hi", "हिन्दी": "hi",
    "marathi": "mr", "मराठी": "mr",
    "tamil": "ta", "தமிழ்": "ta",
    "punjabi": "pa", "ਪੰਜਾਬੀ": "pa",
}


def _sanitize_slots(updates: dict) -> dict:
    """Normalize and drop any slot values that are not in the allowed literal sets."""
    clean: dict = {}
    for k, v in updates.items():
        if k == "primary_language" and isinstance(v, str):
            normalized = _LANG_NORM.get(v.lower(), v)
            if normalized in _VALID_SLOT_VALUES["primary_language"]:
                clean[k] = normalized
        elif k in _VALID_SLOT_VALUES:
            if v in _VALID_SLOT_VALUES[k]:
                clean[k] = v
            # else: silently discard invalid enum value
        else:
            clean[k] = v
    return clean


def _safe_brief(fields: dict) -> Brief:
    while True:
        try:
            return Brief(**fields)
        except ValidationError as exc:
            bad = {str(e["loc"][0]) for e in exc.errors() if e["loc"]}
            if not bad:
                break
            fields = {k: v for k, v in fields.items() if k not in bad}
    return Brief()


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
_PROMPT_PATH = Path(__file__).resolve().parents[4] / "docs" / "prompts" / "conversation_system.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


# Cached Gemini client — instantiating it per turn does a fresh TLS handshake
# and adds 100–300ms to every call.
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


# ── Public turn API (sync — kept for tests / non-SSE callers) ───────────


@dataclass
class TurnResult:
    slot_updates: dict[str, Any]
    next_question: str
    chips: list[str]
    ready: bool


_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


def step(brief: dict[str, Any], user_message: str | None) -> TurnResult:
    """Run one full collect-mode turn through the compiled LangGraph."""
    graph = _get_graph()
    state = graph.invoke({
        "brief": dict(brief or {}),
        "user_message": user_message or "",
        "slot_updates": {},
        "next_question": "",
        "chips": [],
        "ready": False,
    })
    return TurnResult(
        slot_updates=state["slot_updates"],
        next_question=state["next_question"],
        chips=state["chips"],
        ready=state["ready"],
    )


# ── Async streaming API (used by the SSE chat route) ────────────────────


async def astream(
    brief: dict[str, Any],
    user_message: str | None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Stream a collect-mode turn.

    Yields tuples of (event, payload). Events:

      * thinking     — emitted immediately so the SSE connection flushes.
      * slot_update  — partial or final slot extractions.
      * question     — the next question (or clarifying question on `unclear`).
      * ready        — all slots filled; payload has the final brief.
      * done         — terminal event with the accumulated slot updates.
    """
    brief = dict(brief or {})
    msg = (user_message or "").strip()

    # Target slot = the slot the user is currently being asked about.
    target_slot = _next_missing_slot(brief)
    yield ("thinking", {"target_slot": target_slot})

    extracted: dict[str, Any] = {}
    unclear = False
    clarification: str | None = None
    early_question_slot: str | None = None

    if msg:
        heuristic = _sanitize_slots(_heuristic_extract(msg, brief))
        if heuristic:
            extracted.update(heuristic)
            yield ("slot_update", {"slots": heuristic, "partial": True})

            # If the heuristic confidently filled the slot the user was being
            # asked about, we already know the next question. Yield it now so
            # the UI paints it immediately — Gemini will keep streaming tokens
            # and any slot refinements in the background and the front-end
            # treats those as enrichments rather than blockers.
            if target_slot and target_slot in heuristic:
                provisional_brief = {**brief, **extracted}
                next_missing = _missing_slots(provisional_brief)
                if next_missing:
                    nxt = _question_for(next_missing[0])
                    yield ("question", {
                        "prompt": nxt["question"], "chips": nxt["chips"],
                        "target_slot": next_missing[0], "clarify": False,
                    })
                    early_question_slot = next_missing[0]

        seen_keys: set[str] = set()
        # Use bulk extraction (no slot focus) when many slots are still missing so
        # a rich first message can fill all slots in a single Gemini call instead
        # of requiring one round-trip per slot.
        bulk_mode = len(_missing_slots(brief)) >= 5
        stream_target = None if bulk_mode else target_slot
        async for kind, payload in _gemini_stream(msg, brief, stream_target):
            if kind == "partial_slots":
                clean = _sanitize_slots(payload)
                # Only forward keys we haven't already streamed.
                new = {k: v for k, v in clean.items()
                       if k not in seen_keys and extracted.get(k) != v}
                if new:
                    extracted.update(new)
                    seen_keys.update(new.keys())
                    yield ("slot_update", {"slots": new, "partial": True})
            elif kind == "final":
                data = payload or {}
                if isinstance(data, dict):
                    if data.get("unclear") is True and target_slot:
                        unclear = True
                        clarification = data.get("clarification") or None
                    # Accept either {"slot_updates": {...}} or a bare slot dict.
                    raw = data.get("slot_updates") if "slot_updates" in data else {
                        k: v for k, v in data.items()
                        if k not in {"unclear", "clarification",
                                     "next_question", "chips", "ready"}
                    }
                    final_clean = _sanitize_slots(raw if isinstance(raw, dict) else {})
                    new = {k: v for k, v in final_clean.items()
                           if extracted.get(k) != v}
                    if new:
                        extracted.update(new)
                        yield ("slot_update", {"slots": new, "partial": False})

    brief = {**brief, **extracted}

    # If we *just* fired an upload question last turn, the user's reply on
    # this turn is the dismissal/done signal — mark "prompted" so we don't
    # re-ask, then clear the awaiting flag.
    pseudo_updates: dict[str, Any] = {}
    if msg and brief.get("_awaiting_upload"):
        if brief["_awaiting_upload"] == "character":
            pseudo_updates["character_references_prompted"] = True
        elif brief["_awaiting_upload"] == "style":
            pseudo_updates["style_references_prompted"] = True
        pseudo_updates["_awaiting_upload"] = None
        brief.update(pseudo_updates)

    missing = _missing_slots(brief)
    upload_kind = _pending_upload_kind(brief) if not missing else None

    # Decide the next prompt.
    if unclear and target_slot and target_slot in missing:
        if pseudo_updates:
            yield ("slot_update", {"slots": pseudo_updates, "partial": False})
        q = _question_for(target_slot)
        prompt = clarification or (
            f"Hmm — I wasn't sure how to read that. "
            f"Could you pick one of these for {target_slot.replace('_', ' ')}?"
        )
        yield ("question", {
            "prompt": prompt, "chips": q["chips"],
            "target_slot": target_slot, "clarify": True,
        })
    elif missing:
        if pseudo_updates:
            yield ("slot_update", {"slots": pseudo_updates, "partial": False})
        # If we already streamed the same next-question early (heuristic
        # branch above) don't repaint it. If Gemini extracted something that
        # changed which slot is missing, the early prompt is wrong — resend.
        if early_question_slot != missing[0]:
            nxt = _question_for(missing[0])
            yield ("question", {
                "prompt": nxt["question"], "chips": nxt["chips"],
                "target_slot": missing[0], "clarify": False,
            })
    elif upload_kind:
        # All required slots filled; ask for optional references before
        # confirming. Set _awaiting_upload so the next user turn marks the
        # corresponding *_prompted flag and we advance.
        pseudo_updates["_awaiting_upload"] = upload_kind
        yield ("slot_update", {"slots": pseudo_updates, "partial": False})
        q = _upload_question_for(upload_kind)
        yield ("question", {
            "prompt": q["prompt"], "chips": q["chips"],
            "target_slot": q["slot"], "clarify": False,
            "expects": "upload", "upload_kind": upload_kind,
        })
    else:
        if pseudo_updates:
            yield ("slot_update", {"slots": pseudo_updates, "partial": False})
        yield ("question", {
            "prompt": _summary(brief), "chips": ["Start planning"],
            "target_slot": None, "clarify": False,
        })
        yield ("ready", {"brief": brief})

    yield ("done", {"slot_updates": {**extracted, **pseudo_updates}, "brief": brief})


# ── State + nodes (sync LangGraph path) ─────────────────────────────────


class _State(TypedDict):
    brief: dict[str, Any]
    user_message: str
    slot_updates: dict[str, Any]
    next_question: str
    chips: list[str]
    ready: bool


def _node_extract_slots(state: _State) -> _State:
    msg = state["user_message"]
    if not msg:
        return state
    heuristic = _sanitize_slots(_heuristic_extract(msg, state["brief"]))
    gemini = _sanitize_slots(_gemini_extract(msg, state["brief"]) or {})
    extracted = {**heuristic, **gemini}
    state["slot_updates"] = extracted
    state["brief"] = {**state["brief"], **extracted}
    return state


def _node_pick_next_question(state: _State) -> _State:
    missing = _missing_slots(state["brief"])
    if not missing:
        return state  # routed to confirm node next
    nxt = _question_for(missing[0])
    state["next_question"] = nxt["question"]
    state["chips"] = nxt["chips"]
    state["ready"] = False
    return state


def _node_confirm_and_kickoff(state: _State) -> _State:
    state["next_question"] = _summary(state["brief"])
    state["chips"] = ["Start planning"]
    state["ready"] = True
    return state


def _route_after_pick(state: _State) -> str:
    return "confirm" if not _missing_slots(state["brief"]) else "end"


def _build_graph():
    g = StateGraph(_State)
    g.add_node("extract_slots", _node_extract_slots)
    g.add_node("pick_next_question", _node_pick_next_question)
    g.add_node("confirm_and_kickoff", _node_confirm_and_kickoff)
    g.add_edge(START, "extract_slots")
    g.add_edge("extract_slots", "pick_next_question")
    g.add_conditional_edges(
        "pick_next_question",
        _route_after_pick,
        {"confirm": "confirm_and_kickoff", "end": END},
    )
    g.add_edge("confirm_and_kickoff", END)
    return g.compile()


# ── Slot question script (used when LLM doesn't drive the question) ─────


SLOT_QUESTIONS: list[dict[str, Any]] = [
    {"key": "video_type",
     "question": "Hey — let's plan your video. What kind are we making?",
     "chips": ["Explainer", "Cinematic", "Social reel", "Ad"]},
    {"key": "topic",
     "question": "Got it. What's it about? A sentence is enough.",
     "chips": ["Coffee brand launch", "Fitness app", "B2B onboarding", "Travel destination"]},
    {"key": "visual_style",
     "question": "What visual style are you going for?",
     "chips": ["realistic", "animated", "documentary", "minimalist"]},
    {"key": "duration_seconds",
     "question": "About how long should it be?",
     "chips": ["15", "30", "45", "60"]},
    {"key": "aspect_ratio",
     "question": "Which aspect ratio? This affects framing.",
     "chips": ["9:16", "16:9", "1:1"]},
    {"key": "primary_language",
     "question": "Which language for narration and subtitles? (Default: English)",
     "chips": ["English", "Hindi", "Marathi", "Tamil", "Punjabi"]},
    {"key": "narration_tone",
     "question": "What tone should the narration carry?",
     "chips": ["energetic", "calm", "authoritative", "friendly"]},
    {"key": "has_characters",
     "question": "Should there be people on camera, or voice-over only?",
     "chips": ["Voice-over only", "A presenter", "A small group", "Background extras only"]},
    {"key": "music_enabled",
     "question": "Want a background music bed under the narration?",
     "chips": ["Yes, music please", "No, voice only"]},
    {"key": "subtitles_enabled",
     "question": "Burn in subtitles?",
     "chips": ["Yes, burn them in", "No subtitles"]},
]


def _question_for(slot: str) -> dict[str, Any]:
    for q in SLOT_QUESTIONS:
        if q["key"] == slot:
            return q
    return {"question": f"Tell me about {slot}.", "chips": []}


# ── Optional reference-upload questions ────────────────────────────────
#
# Fired after all required slots are filled but before "ready". Lets the
# user attach character / style reference photos that lock the look of the
# storyboard from the very first render. Each kind is asked at most once
# per project (gated by ``*_references_prompted`` flags stored on the
# brief). Skippable by sending any text reply.


UPLOAD_QUESTIONS: dict[str, dict[str, Any]] = {
    "character": {
        "slot":   "character_references",
        "prompt": (
            "Quick optional step — got reference photos for the people in your "
            "video? Uploading even one helps lock the look so the same face "
            "shows up across every scene. You can skip and just describe them "
            "in the script."
        ),
        "chips": ["Upload character photos", "Skip — invent the cast"],
    },
    "style": {
        "slot":   "style_references",
        "prompt": (
            "Optional: any mood-board, palette, or location photos you'd like "
            "me to match? I'll pull colour, lighting, and atmosphere from them."
        ),
        "chips": ["Upload style references", "Skip — use the visual style"],
    },
}


def _upload_question_for(kind: str) -> dict[str, Any]:
    return UPLOAD_QUESTIONS.get(kind, {
        "slot": f"{kind}_references",
        "prompt": f"Got reference images for {kind}? Optional.",
        "chips":  [f"Upload {kind} references", "Skip"],
    })


def _pending_upload_kind(brief: dict[str, Any]) -> str | None:
    """Pick which (if any) optional reference-upload question to fire next.

    Character takes priority over style. Each fires at most once per
    project, gated by the ``*_references_prompted`` flag.
    """
    if brief.get("has_characters") and not brief.get("character_references_prompted"):
        return "character"
    if brief.get("visual_style") and not brief.get("style_references_prompted"):
        return "style"
    return None


def _missing_slots(brief: dict[str, Any]) -> list[str]:
    fields = {k: v for k, v in brief.items() if k in Brief.model_fields}
    return _safe_brief(fields).missing()


def _next_missing_slot(brief: dict[str, Any]) -> str | None:
    missing = _missing_slots(brief)
    return missing[0] if missing else None


def _summary(brief: dict[str, Any]) -> str:
    return (
        f"Got it — a {brief.get('duration_seconds')}s {brief.get('visual_style')} "
        f"{brief.get('video_type', 'video')} in {brief.get('aspect_ratio')}, "
        f"narrated in {brief.get('primary_language', 'en')}. "
        "Ready to plan the scenes."
    )


# ── Heuristic fallback (no LLM) ─────────────────────────────────────────


_LANG_ALIASES = {
    "english": "en", "en": "en",
    "hindi": "hi", "हिन्दी": "hi",
    "marathi": "mr", "मराठी": "mr",
    "tamil": "ta", "தமிழ்": "ta",
    "punjabi": "pa", "ਪੰਜਾਬੀ": "pa",
}
_TYPE_ALIASES = {
    "explainer": "explainer", "cinematic": "cinematic",
    "ad": "ad", "advert": "ad", "advertisement": "ad",
    "social": "social_reel", "reel": "social_reel",
    "tiktok": "social_reel", "instagram": "social_reel",
}
_STYLE_ALIASES = {
    "realistic": "realistic", "real": "realistic",
    "animated": "animated", "animation": "animated", "cartoon": "animated",
    "documentary": "documentary", "doc": "documentary",
    "minimalist": "minimalist", "minimal": "minimalist", "clean": "minimalist",
}
_TONE_ALIASES = {
    "energetic": "energetic", "energy": "energetic", "upbeat": "energetic",
    "calm": "calm", "soft": "calm", "gentle": "calm",
    "authoritative": "authoritative", "serious": "authoritative",
    "friendly": "friendly", "warm": "friendly",
}
_ASPECT_ALIASES = {
    "9:16": "9:16", "vertical": "9:16", "portrait": "9:16",
    "16:9": "16:9", "wide": "16:9", "landscape": "16:9",
    "1:1": "1:1", "square": "1:1",
}


def _heuristic_extract(msg: str, brief: dict[str, Any]) -> dict[str, Any]:
    text = msg.strip()
    low = text.lower()
    out: dict[str, Any] = {}

    _explicit_lang_phrases = (
        "narrate in ", "narration in ", "voice in ", "voice-over in ",
        "voiceover in ", "language: ", "in english", "in hindi",
        "in marathi", "in tamil", "in punjabi",
        "english voice", "hindi voice", "tamil narration", "marathi narration",
    )
    _is_explicit_lang = (
        low in _LANG_ALIASES
        or any(low.startswith(p) or p in low for p in _explicit_lang_phrases)
    )
    if _is_explicit_lang:
        for k, v in _LANG_ALIASES.items():
            if k in low:
                out["primary_language"] = v
                break
    for k, v in _TYPE_ALIASES.items():
        if k in low:
            out["video_type"] = v
            break
    for k, v in _STYLE_ALIASES.items():
        if k in low:
            out["visual_style"] = v
            break
    for k, v in _TONE_ALIASES.items():
        if k in low:
            out["narration_tone"] = v
            break
    for k, v in _ASPECT_ALIASES.items():
        if k in low:
            out["aspect_ratio"] = v
            break
    m = re.search(r"\b(\d{1,3})\s*s(?:ec(?:onds?)?)?\b", low) or re.search(r"\b(\d{1,3})\b", low)
    if m and "duration_seconds" not in brief:
        try:
            n = int(m.group(1))
            if 5 <= n <= 180:
                out["duration_seconds"] = n
        except Exception:
            pass
    if any(k in low for k in ("voice-over only", "voice over only", "voiceover")):
        out["has_characters"] = False
    elif any(k in low for k in ("presenter", "person", "people", "speaker", "on camera")):
        out["has_characters"] = True

    # music_enabled / subtitles_enabled chip mapping. Only fire when the
    # user message looks like an answer to the matching question — match
    # the chip phrasing or unambiguous yes/no in context.
    if "music" in low or any(p in low for p in ("background bed", "score", "soundtrack")):
        if any(p in low for p in ("no music", "no, voice", "voice only", "without music", "no, voice only")):
            out["music_enabled"] = False
        elif any(p in low for p in ("yes", "music please", "with music", "want music", "add music")):
            out["music_enabled"] = True
    if "subtitle" in low or "captions" in low:
        if any(p in low for p in ("no subtitle", "no captions", "without subtitle", "no, ", "off")):
            out["subtitles_enabled"] = False
        elif any(p in low for p in ("yes", "burn", "with subtitle", "with captions", "on")):
            out["subtitles_enabled"] = True
    if not out and "topic" not in brief and len(text) >= 4:
        out["topic"] = text
    return out


# ── Gemini extraction ───────────────────────────────────────────────────


@lru_cache(maxsize=32)
def _build_system_prompt(target_slot: str | None) -> str:
    """Base system prompt + a slot-targeted hint when we know which slot the
    user is answering."""
    sys = SYSTEM_PROMPT or (
        "Extract any inferable slot values. Return JSON keys from: "
        "video_type, visual_style, duration_seconds, primary_language, "
        "narration_tone, has_characters, aspect_ratio, topic. Omit unknowns."
    )
    if not target_slot:
        return sys

    options = sorted(_VALID_SLOT_VALUES.get(target_slot, set()))
    hint = [
        "",
        f"CURRENT SLOT BEING ANSWERED: `{target_slot}`.",
    ]
    if options:
        hint.append(f"Allowed values for this slot: {options}.")
    hint.append(
        "Map the user's reply (even if creative or oblique) to one of the "
        "allowed values when you reasonably can — synonyms, paraphrases, "
        "and aesthetic references all count. For free-text slots (topic, "
        "overlay_description) accept any reasonable string."
    )
    hint.append(
        "If the user's reply genuinely cannot be mapped to this slot, "
        'instead return: {"slot_updates": {}, "unclear": true, '
        '"clarification": "<one short friendly follow-up question>"}. '
        "Do NOT repeat the original question verbatim — phrase the "
        "clarification differently and give a concrete example or two."
    )
    return sys + "\n\n" + "\n".join(hint)


def _gemini_extract(user_message: str, brief: dict[str, Any]) -> dict[str, Any] | None:
    """Synchronous, non-streaming extraction. Used by the LangGraph path."""
    client = _get_gemini_client()
    if client is None:
        return None
    try:
        from google.genai import types

        target = _next_missing_slot(brief)
        sys = _build_system_prompt(target)
        prompt = (
            f"Existing brief:\n{json.dumps(brief, default=str)}\n\n"
            f"User said:\n{user_message}\n\nReturn JSON only."
        )
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=sys,
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        data = json.loads(resp.text or "{}")
        if isinstance(data, dict):
            updates = data.get("slot_updates") if "slot_updates" in data else data
            return updates if isinstance(updates, dict) else None
        return None
    except Exception:
        return None


# ── Partial JSON parser for streaming slot extraction ──────────────────


_SLOT_PAIR_RE = re.compile(
    r'"(?P<key>[A-Za-z_]\w*)"\s*:\s*'
    r'(?:"(?P<str>(?:\\.|[^"\\])*)"|'
    r'(?P<int>-?\d+)|'
    r'(?P<bool>true|false)|'
    r'(?P<null>null))'
)


def _extract_completed_pairs(buf: str) -> dict[str, Any]:
    """Pull `"key": value` pairs out of the partial JSON streamed so far.

    We look inside the `"slot_updates": { ... }` object boundary; if that key
    hasn't been emitted yet we fall back to the whole buffer (Gemini sometimes
    emits a bare slot dict before wrapping).
    """
    sub = buf
    start = buf.find('"slot_updates"')
    if start != -1:
        brace = buf.find("{", start)
        if brace != -1:
            close = buf.find("}", brace + 1)
            sub = buf[brace + 1:close] if close != -1 else buf[brace + 1:]
    out: dict[str, Any] = {}
    for m in _SLOT_PAIR_RE.finditer(sub):
        k = m.group("key")
        if k in {"slot_updates", "next_question", "chips", "ready",
                 "clarification", "unclear"}:
            continue
        if m.group("str") is not None:
            out[k] = m.group("str")
        elif m.group("int") is not None:
            try:
                out[k] = int(m.group("int"))
            except ValueError:
                pass
        elif m.group("bool") is not None:
            out[k] = m.group("bool") == "true"
        # null → omit
    return out


async def _gemini_stream(
    user_message: str,
    brief: dict[str, Any],
    target_slot: str | None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Async streaming extraction. Yields:

      * ("partial_slots", {...})  — newly-completed key/value pairs as they arrive.
      * ("final", {...})           — the fully parsed JSON object (or None on parse failure).

    Returns silently when no API key is set, so callers fall through to the
    heuristic-only path.
    """
    client = _get_gemini_client()
    if client is None:
        return
    try:
        from google.genai import types
    except Exception:
        return

    try:
        sys = _build_system_prompt(target_slot)
        prompt = (
            f"Existing brief:\n{json.dumps(brief, default=str)}\n\n"
            f"User said:\n{user_message}\n\nReturn JSON only."
        )
        # Omit response_mime_type so Gemini streams tokens immediately.
        # JSON mode buffers the full object before flushing — removing it lets
        # _extract_completed_pairs parse partial JSON as tokens arrive.
        config = types.GenerateContentConfig(
            system_instruction=sys,
            temperature=0.0,
        )

        buf = ""
        seen: set[str] = set()
        # The async streaming entrypoint changed across google-genai versions;
        # try the modern form first, fall back to the older awaitable.
        stream_call = client.aio.models.generate_content_stream(
            model=GEMINI_MODEL, contents=[prompt], config=config,
        )
        try:
            stream = await stream_call  # older SDK: returns coroutine
        except TypeError:
            stream = stream_call         # newer SDK: returns async iterator directly

        async for chunk in stream:
            text = getattr(chunk, "text", "") or ""
            if not text:
                continue
            buf += text
            # Forward raw text chunks so the chat surface can render the LLM's
            # output as it streams. Architecture.md §7 chat SSE contract.
            yield ("token", {"text": text})
            new_pairs = {
                k: v for k, v in _extract_completed_pairs(buf).items()
                if k not in seen
            }
            if new_pairs:
                seen.update(new_pairs.keys())
                yield ("partial_slots", new_pairs)

        try:
            data = json.loads(buf or "{}")
        except Exception:
            data = None
        yield ("final", data if isinstance(data, dict) else {})
    except Exception:
        # Swallow streaming failures — caller already has the heuristic.
        return
