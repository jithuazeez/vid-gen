"""Gemini wrapper for inside-Modal calls (used by scene engine reruns,
edit router, and any worker that needs structured generation).

The API service has its own LangGraph orchestrator; this module exists so
Modal functions can call Gemini without depending on the API package.
"""
from __future__ import annotations

import json
import os
from typing import Any


DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")


def generate_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.4,
) -> dict[str, Any] | None:
    """Call Gemini and parse the response as JSON. Returns None on failure."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model or DEFAULT_MODEL,
            contents=[user],
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=temperature,
            ),
        )
        text = resp.text or "{}"
        return json.loads(text)
    except Exception:
        return None
