"""Single LangGraph object that wraps the two chat subgraphs.

Architecture.md §13: "One LangGraph object with two compiled subgraphs —
collect and edit — selected at the entry router node by `project.status`."

This module is the parent graph. Its entry router (`pick_mode`) reads
`project_status` from the state and routes to either the compiled
collect subgraph or the compiled edit subgraph. Callers no longer need
to branch in the SSE route handler — they hand the parent graph the
status and message, and get the right behaviour back.

The two subgraph builders live in their original modules
(`conversation._build_graph`, `edit_router._build_graph`) so the rest
of the codebase keeps working.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.orchestrators import conversation, edit_router

Mode = Literal["collect", "edit"]


class ChatState(TypedDict, total=False):
    project_status: str
    mode: Mode

    # collect-mode fields (mirror conversation._State)
    brief: dict[str, Any]
    user_message: str
    slot_updates: dict[str, Any]
    next_question: str
    chips: list[str]
    ready: bool

    # edit-mode fields (mirror edit_router._State)
    message: str
    intent: str
    args: dict[str, Any]
    confidence: float
    preview: str
    candidates: list[str]


_COLLECT_SUBGRAPH = None
_EDIT_SUBGRAPH = None
_PARENT = None


def mode_for_status(status: str | None) -> Mode:
    """Architecture §13: collect for {draft, collecting}; edit otherwise."""
    return "collect" if (status or "draft") in {"draft", "collecting"} else "edit"


def _node_pick_mode(state: ChatState) -> ChatState:
    state["mode"] = mode_for_status(state.get("project_status"))
    return state


def _route_by_mode(state: ChatState) -> str:
    return state.get("mode") or "collect"


def _node_run_collect(state: ChatState) -> ChatState:
    sub_state = {
        "brief": dict(state.get("brief") or {}),
        "user_message": state.get("user_message", "") or state.get("message", ""),
        "slot_updates": {},
        "next_question": "",
        "chips": [],
        "ready": False,
    }
    out = _collect_subgraph().invoke(sub_state)
    state.update(out)
    return state


def _node_run_edit(state: ChatState) -> ChatState:
    sub_state = {
        "message": state.get("message", "") or state.get("user_message", ""),
        "intent": "unknown",
        "args": {},
        "confidence": 0.0,
        "preview": "",
        "candidates": [],
    }
    out = _edit_subgraph().invoke(sub_state)
    state.update(out)
    return state


def _collect_subgraph():
    global _COLLECT_SUBGRAPH
    if _COLLECT_SUBGRAPH is None:
        _COLLECT_SUBGRAPH = conversation._build_graph()
    return _COLLECT_SUBGRAPH


def _edit_subgraph():
    global _EDIT_SUBGRAPH
    if _EDIT_SUBGRAPH is None:
        _EDIT_SUBGRAPH = edit_router._build_graph()
    return _EDIT_SUBGRAPH


def parent_graph():
    """Compile (once) and return the parent graph that fans out to subgraphs."""
    global _PARENT
    if _PARENT is None:
        g = StateGraph(ChatState)
        g.add_node("pick_mode", _node_pick_mode)
        g.add_node("collect_subgraph", _node_run_collect)
        g.add_node("edit_subgraph", _node_run_edit)
        g.add_edge(START, "pick_mode")
        g.add_conditional_edges(
            "pick_mode",
            _route_by_mode,
            {"collect": "collect_subgraph", "edit": "edit_subgraph"},
        )
        g.add_edge("collect_subgraph", END)
        g.add_edge("edit_subgraph", END)
        _PARENT = g.compile()
    return _PARENT


def route_turn(*, project_status: str, brief: dict[str, Any] | None,
               message: str) -> ChatState:
    """One-shot entry point used by tests and any non-SSE caller.

    The SSE chat route still calls `conversation.astream` / `edit_router.classify`
    directly because it needs token-level streaming and async semantics that
    LangGraph's sync `.invoke` doesn't expose. Both paths hit the same
    underlying subgraph builders, so behaviour is identical.
    """
    return parent_graph().invoke({
        "project_status": project_status,
        "brief": brief or {},
        "user_message": message,
        "message": message,
    })
