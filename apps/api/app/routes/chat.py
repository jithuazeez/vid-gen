"""POST /projects/:id/chat — SSE chat endpoint.

Architecture.md §7. Mode is picked from project.status:
  draft / collecting           → collect mode (slot-fill, streaming)
  planning / ready / completed → edit mode (intent router)
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.celery_client import send as send_celery
from app.db import get_session
from app.db.models import Character, ConversationMessage, Project, Scene
from app.orchestrators import conversation, edit_router, scene_regen
from app.orchestrators.chat_graph import mode_for_status

router = APIRouter(prefix="/projects", tags=["chat"])


class ChatBody(BaseModel):
    message: str


@router.post("/{project_id}/chat")
async def chat(
    project_id: uuid.UUID,
    body: ChatBody,
    session: AsyncSession = Depends(get_session),
) -> EventSourceResponse:
    project = await _load(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Persist the user message immediately (fire-and-forget would lose it).
    session.add(ConversationMessage(
        project_id=project.id, role="user", content=body.message,
    ))
    await session.commit()
    await session.refresh(project)

    # Architecture §13: the mode comes from the unified parent graph's
    # entry router so this branch and the LangGraph stay in lockstep.
    if mode_for_status(project.status) == "collect":
        return EventSourceResponse(_collect_stream(session, project, body.message))
    return EventSourceResponse(_edit_stream(session, project, body.message))


# ─────────────────────────────────────────────────────────────────────
# Collect mode — progressive streaming
# ─────────────────────────────────────────────────────────────────────


async def _collect_stream(session: AsyncSession, project: Project,
                          message: str) -> AsyncIterator[dict[str, str]]:
    accum_updates: dict[str, Any] = {}
    last_question = ""
    last_chips: list[str] = []
    last_clarify = False
    ready = False
    final_brief: dict[str, Any] = dict(project.brief or {})

    async for kind, payload in conversation.astream(project.brief or {}, message):
        if kind == "thinking":
            yield _evt("thinking", payload)

        elif kind == "token":
            # Forward raw LLM tokens to the client per §7 chat SSE contract.
            yield _evt("token", payload)

        elif kind == "slot_update":
            updates = _coerce_slots(payload.get("slots", {}))
            if not updates:
                continue
            accum_updates.update(updates)
            # Stage in-memory only; we commit once at the end of the turn.
            # Per-chunk commits added one DB round-trip between every streamed
            # slot and slowed the user-visible event stream noticeably.
            project.brief = {**(project.brief or {}), **accum_updates}
            _apply_typed_columns(project, updates)
            if project.status == "draft":
                project.status = "collecting"
            yield _evt("slot_update", {
                "slots": updates,
                "partial": payload.get("partial", False),
            })

        elif kind == "question":
            last_question = payload.get("prompt", "")
            last_chips = payload.get("chips", [])
            last_clarify = bool(payload.get("clarify", False))
            yield _evt("question", {
                "prompt": last_question,
                "chips": last_chips,
                "clarify": last_clarify,
                "target_slot": payload.get("target_slot"),
                "expects": payload.get("expects"),
                "upload_kind": payload.get("upload_kind"),
            })

        elif kind == "ready":
            ready = True
            final_brief = payload.get("brief") or final_brief
            yield _evt("ready", {"brief": final_brief})

        elif kind == "done":
            final_brief = payload.get("brief") or final_brief

    # Final persistence: capture the assistant message + any straggling slot
    # state. Most of the brief was already saved per-event above.
    session.add(ConversationMessage(
        project_id=project.id,
        role="assistant",
        content=last_question,
        tool_calls={
            "slot_updates": accum_updates,
            "ready": ready,
            "clarify": last_clarify,
        },
    ))
    await session.commit()
    yield _evt("done", {})


def _apply_typed_columns(project: Project, updates: dict[str, Any]) -> None:
    """Mirror selected slot updates onto typed ORM columns."""
    if "primary_language" in updates:
        project.primary_language = updates["primary_language"]
        if not project.active_language:
            project.active_language = updates["primary_language"]
    if "aspect_ratio" in updates:
        project.aspect_ratio = updates["aspect_ratio"]
    if "duration_seconds" in updates:
        project.duration_seconds = updates["duration_seconds"]
    if "has_characters" in updates:
        project.has_characters = bool(updates["has_characters"])
    if "music_enabled" in updates:
        project.music_enabled = bool(updates["music_enabled"])


# ─────────────────────────────────────────────────────────────────────
# Edit mode
# ─────────────────────────────────────────────────────────────────────


async def _build_router_context(session: AsyncSession, project: Project) -> dict[str, Any]:
    """Snapshot the storyboard for the edit-router LLM.

    Cheap two-query summary: scenes (ordered) + cast names. Lets the router
    resolve "the last scene", "Mira's scene", invalid scene numbers, etc.
    """
    scenes_res = await session.execute(
        select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_index)
    )
    scenes = scenes_res.scalars().all()
    chars_res = await session.execute(
        select(Character.id, Character.name).where(Character.project_id == project.id)
    )
    chars = chars_res.all()
    name_by_id = {c.id: c.name for c in chars}

    def _summary(s: Scene) -> str:
        text = (s.narration_script or s.visual_prompt or "").strip().replace("\n", " ")
        return text[:120]

    return {
        "scene_count": len(scenes),
        "scenes": [
            {
                "index": s.scene_index,
                "summary": _summary(s),
                "has_speaker": s.has_speaker,
                "character_names": [
                    name_by_id[cid] for cid in (s.character_ids or []) if cid in name_by_id
                ],
            }
            for s in scenes
        ],
        "characters": [c.name for c in chars],
        "active_language": project.active_language or project.primary_language or "en",
        "primary_language": project.primary_language or "en",
    }


async def _edit_stream(session: AsyncSession, project: Project,
                       message: str) -> AsyncIterator[dict[str, str]]:
    yield _evt("thinking", {})
    router_ctx = await _build_router_context(session, project)
    intent = await edit_router.aclassify(message, router_ctx)

    queued = False
    applied = False
    note: str | None = None

    # Architecture.md §13: low confidence → clarification chips, no mutation.
    if intent.confidence < 0.6 and intent.intent != "ask_question":
        chips = intent.clarification_chips()
        yield _evt("question", {
            "prompt": "I'm not sure what you'd like to do — which is closer?",
            "chips": chips, "clarify": True, "target_intent": intent.intent,
        })
        yield _evt("intent", {"intent": intent.intent, "args": intent.args,
                              "preview": intent.preview, "queued": False,
                              "applied": False, "low_confidence": True,
                              "candidates": intent.candidates})

    elif intent.intent == "change_language":
        # Destructive (re-renders); enqueue but ask for confirmation chips.
        send_celery("worker.render.language", str(project.id),
                    intent.args.get("language"))
        queued = True
        yield _evt("intent", {"intent": intent.intent, "args": intent.args,
                              "preview": intent.preview, "queued": True,
                              "applied": False})

    elif intent.intent == "edit_scene":
        # Apply field-level edits directly (low cost, reversible). Architecture
        # §13: "translates intent into PATCH / regenerate calls."
        scene_index = intent.args.get("scene_index")
        field = intent.args.get("field")
        value = intent.args.get("value")
        applied = await _apply_scene_edit(session, project.id, scene_index,
                                          field, value)
        note = ("Applied." if applied
                else "Couldn't find that scene/field to edit.")
        yield _evt("intent", {"intent": intent.intent, "args": intent.args,
                              "preview": intent.preview, "queued": False,
                              "applied": applied, "note": note})

    elif intent.intent == "regenerate_scene":
        # Two-step destructive flow:
        #   1. Rewrite the scene's visual_prompt + narration_script using the
        #      scene_regen orchestrator (cheap LLM call, instant feedback).
        #   2. Enqueue the render so LTX + TTS + composite refresh the assets.
        scene_index = intent.args.get("scene_index")
        modifier = intent.args.get("prompt_modifier") or message
        rewrite = await scene_regen.regenerate(
            session=session, project=project,
            scene_index=int(scene_index) if scene_index is not None else None,
            user_modifier=modifier,
        )
        if rewrite is None:
            yield _evt("intent", {"intent": intent.intent, "args": intent.args,
                                  "preview": intent.preview, "queued": False,
                                  "applied": False,
                                  "note": "Couldn't find that scene to regenerate."})
        else:
            send_celery("worker.render.scene", str(project.id), str(rewrite["scene_id"]))
            queued = True
            yield _evt("intent", {
                "intent": intent.intent,
                "args": {**intent.args, "scene_id": str(rewrite["scene_id"])},
                "preview": intent.preview,
                "queued": True, "applied": True,
                "note": rewrite.get("continuity_notes") or "Rewriting and re-rendering this scene.",
            })

    elif intent.intent == "edit_overlay":
        yield _evt("intent", {"intent": intent.intent, "args": intent.args,
                              "preview": intent.preview, "queued": False,
                              "applied": False,
                              "note": "Use the timeline controls to confirm."})

    else:
        yield _evt("intent", {"intent": intent.intent, "args": intent.args,
                              "preview": intent.preview, "queued": False,
                              "applied": False})

    session.add(ConversationMessage(
        project_id=project.id, role="assistant", content=intent.preview,
        tool_calls={"intent": intent.intent, "args": intent.args,
                    "confidence": intent.confidence,
                    "queued": queued, "applied": applied, "note": note},
    ))
    await session.commit()
    yield _evt("done", {})


async def _apply_scene_edit(
    session: AsyncSession, project_id: uuid.UUID,
    scene_index: int | None, field: str | None, value: Any,
) -> bool:
    """Apply a chat-driven edit_scene intent in-band.

    Resolves the scene by (project_id, scene_index) — the LLM speaks in
    1-based indices, which is what the schema stores. Returns True on apply.
    """
    if scene_index is None or field is None:
        return False
    if field not in {"narration_script", "visual_prompt",
                     "has_speaker", "subtitle_position"}:
        return False
    from app.db.models import Scene
    res = await session.execute(
        select(Scene).where(
            Scene.project_id == project_id,
            Scene.scene_index == int(scene_index),
        )
    )
    scene = res.scalar_one_or_none()
    if scene is None:
        return False
    if field == "has_speaker":
        value = bool(value) if not isinstance(value, str) else (
            value.strip().lower() in {"true", "yes", "on", "1"})
    setattr(scene, field, value)
    await session.commit()
    return True


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


async def _load(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    res = await session.execute(select(Project).where(Project.id == project_id))
    return res.scalar_one_or_none()


def _evt(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}


def _coerce_slots(slots: dict[str, Any]) -> dict[str, Any]:
    """Coerce slot values to their expected Python types.

    Gemini sometimes returns integers/booleans as strings (e.g. "30", "true").
    Normalize them so writing to typed ORM columns doesn't raise DataError.
    """
    out = dict(slots)
    if "duration_seconds" in out:
        try:
            out["duration_seconds"] = int(out["duration_seconds"])
        except (ValueError, TypeError):
            out.pop("duration_seconds")
    for key in ("has_characters", "music_enabled"):
        if key in out and isinstance(out[key], str):
            out[key] = out[key].lower() not in {"false", "0", "no", ""}
    return out
