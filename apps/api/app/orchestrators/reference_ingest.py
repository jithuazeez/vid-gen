"""Vision ingest for user-uploaded reference images.

Loads ``docs/prompts/reference_ingest_system.md`` and calls Gemini 3.1
Flash-Lite multimodal with the image attached as a base64-encoded
``inline_data`` part. The model returns a kind-specific descriptor JSON
which is stored on the asset's ``metadata`` JSONB column and later read by
``scene_regen.py``.

No separate vision model required — Flash-Lite is multimodal and is the
same model used by the rest of the orchestrator layer.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROMPT_PATH = _REPO_ROOT / "docs" / "prompts" / "reference_ingest_system.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""

Kind = Literal["character", "style", "environment"]


def ingest(*, image_bytes: bytes, mime_type: str, kind: Kind) -> dict[str, Any]:
    """Describe an uploaded reference image. Returns a descriptor dict.

    On any failure (no API key, network, parse), returns a degraded
    descriptor with ``{"kind": kind, "error": "<reason>"}`` so the caller
    can still persist the asset row and the user can re-trigger ingest
    later.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or ""
    if not api_key or not SYSTEM_PROMPT:
        return {"kind": kind, "error": "reference_ingest not configured (missing GEMINI_API_KEY or prompt)"}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        instruction_part = types.Part.from_text(text=f"kind: {kind}")

        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=[image_part, instruction_part])],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        data = json.loads(resp.text or "{}")
        if not isinstance(data, dict):
            return {"kind": kind, "error": "model returned non-object JSON"}
        # Ensure kind field is present and matches.
        data["kind"] = kind
        return data
    except Exception as exc:
        return {"kind": kind, "error": f"ingest failed: {type(exc).__name__}: {exc}"}
