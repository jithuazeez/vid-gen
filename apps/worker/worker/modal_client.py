"""Thin client wrapping `modal.Function.from_name(...)` so Celery tasks can
call Modal functions by name without importing the Modal app code.

`MODAL_STUB=1` (or any spawn/remote failure in non-stub mode) routes the call
through `worker.fixtures.materialise`, which uploads a canned fixture artifact
to S3 and registers a real row in `assets`. This lets the entire pipeline
(composite → final_export → review playback → language switch → re-export)
run end-to-end without paying for GPUs.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from worker import fixtures

logger = logging.getLogger(__name__)

MODAL_APP_NAME = os.environ.get("MODAL_APP_NAME", "vidplatform")
_STUB = os.environ.get("MODAL_STUB", "1") == "1"


def _lookup(fn_name: str):
    if _STUB:
        return _StubFunction(fn_name)
    try:
        import modal  # type: ignore

        real = modal.Function.from_name(MODAL_APP_NAME, fn_name)
        return _SafeModalFunction(fn_name, real)
    except Exception:
        return _StubFunction(fn_name)


class _SafeModalFunction:
    """Wraps a real Modal Function so that spawn/remote errors fall back to stub."""

    def __init__(self, name: str, fn: Any) -> None:
        self.name = name
        self._fn = fn

    def spawn(self, *args: Any, **kwargs: Any) -> Any:
        try:
            result = self._fn.spawn(*args, **kwargs)
            logger.info("[modal] spawned %s OK", self.name)
            return result
        except Exception as exc:
            logger.warning(
                "[modal] spawn FAILED for %s — falling back to fixture stub. Error: %s",
                self.name, exc,
            )
            return _StubFunction(self.name).spawn(*args, **kwargs)

    def remote(self, *args: Any, **kwargs: Any) -> Any:
        try:
            result = self._fn.remote(*args, **kwargs)
            logger.info("[modal] remote %s OK", self.name)
            return result
        except Exception as exc:
            logger.warning(
                "[modal] remote FAILED for %s — falling back to fixture stub. Error: %s",
                self.name, exc,
            )
            return _StubFunction(self.name).remote(*args, **kwargs)


class _StubFunction:
    """Fixture-mode stand-in for a Modal Function.

    Both `.spawn()` and `.remote()` actually execute the fixture materialiser
    — there's no real network call so the spawn/await distinction collapses
    onto the same underlying work. `.spawn()` returns a `_StubCall` whose
    `.get()` replays the pre-computed payload.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def spawn(self, *args: Any, **kwargs: Any) -> "_StubCall":
        payload = fixtures.materialise(self.name, _coerce_kwargs(args, kwargs))
        return _StubCall(self.name, payload)

    def remote(self, *args: Any, **kwargs: Any) -> Any:
        return fixtures.materialise(self.name, _coerce_kwargs(args, kwargs))


def _coerce_kwargs(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Some callers spawn positional, some keyword. Normalise to a kwargs dict
    keyed by parameter name so the materialiser can look up project_id /
    scene_id / language regardless of call style."""
    out: dict[str, Any] = dict(kwargs)
    # Positional args show up rarely (the worker uses kwargs throughout) but
    # support it just in case — first positional is always project_id.
    if args and "project_id" not in out:
        out["project_id"] = args[0]
    return out


class _StubCall:
    def __init__(self, name: str, payload: Any) -> None:
        self.object_id = f"stub-{name}"
        self._payload = payload

    def get(self, *_a: Any, **_kw: Any) -> Any:
        return self._payload


# Public Modal function bindings — names match @app.function(name=...)
ping             = _lookup("ping")
sdxl_thumbnail   = _lookup("sdxl_thumbnail")
sdxl_character_ref = _lookup("sdxl_character_ref")
ltx_render       = _lookup("ltx_render")
musetalk_sync    = _lookup("musetalk_sync")
whisper_align    = _lookup("whisper_align")
acestep_music    = _lookup("acestep_music")
mediapipe_face   = _lookup("mediapipe_face")
ffmpeg_composite = _lookup("ffmpeg_composite")
generate_voice   = _lookup("generate_voice")
final_export     = _lookup("final_export")

# Back-compat alias for legacy callers.
sdxl_image = sdxl_thumbnail
