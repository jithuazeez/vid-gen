"""Fixture-mode helpers for `MODAL_STUB=1`.

When the worker can't reach Modal (CI, local dev without credentials, or any
time you want to exercise the orchestrator end-to-end without paying for
GPUs), the modal-client stubs route every spawn/remote call through here.

Each stub upload registers a real row in `assets` pointing at a real object
in S3, so the rest of the pipeline (composite → final_export → review
page playback, language switch, export download) all behave exactly as they
would in production — just with the same canned MP4 / minimal PNG / silent
WAV / one-line SRT swapped in for every artifact.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from worker import db

logger = logging.getLogger(__name__)

# ─── Asset-type metadata ────────────────────────────────────────────────
# Maps the Modal function name to (asset_type, file extension, mime type).
# `ping` deliberately omitted — it doesn't produce an asset.

_ASSET_TYPE_BY_FN: dict[str, tuple[str, str, str]] = {
    "sdxl_thumbnail":     ("thumbnail",     "png", "image/png"),
    "sdxl_character_ref": ("character_ref", "png", "image/png"),
    "ltx_render":         ("scene_video",   "mp4", "video/mp4"),
    "musetalk_sync":      ("lipsync_video", "mp4", "video/mp4"),
    "whisper_align":      ("subtitle_srt",  "srt", "application/x-subrip"),
    "mediapipe_face":     ("face_data",     "json", "application/json"),
    "ffmpeg_composite":   ("composite",     "mp4", "video/mp4"),
    "generate_voice":     ("voice",         "wav", "audio/wav"),
    "final_export":       ("final_export",  "mp4", "video/mp4"),
}


# ─── Fixture bytes ──────────────────────────────────────────────────────


def _fixtures_dir() -> Path | None:
    for candidate in (
        Path(__file__).resolve().parents[2] / "modal_app" / "fixtures",
        Path("/app/apps/modal_app/fixtures"),
    ):
        if candidate.exists():
            return candidate
    return None


# 1×1 transparent PNG.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

# 44-byte WAV header with zero PCM samples — playable but silent.
_WAV_HEADER = (
    b"RIFF\x24\x00\x00\x00WAVEfmt "
    b"\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00"
    b"\x02\x00\x10\x00data\x00\x00\x00\x00"
)

_SRT_TEXT = (
    "1\n"
    "00:00:00,000 --> 00:00:01,000\n"
    "(stub subtitles)\n\n"
).encode()


def _fixture_bytes(ext: str) -> bytes:
    """Return raw bytes for the fixture matching `ext`."""
    if ext == "mp4":
        d = _fixtures_dir()
        if d is not None:
            mp4 = d / "sample.mp4"
            if mp4.exists():
                return mp4.read_bytes()
        # Fallback: empty file — playback will fail but pipeline still
        # registers the row, which is the goal.
        return b""
    if ext == "png":
        return _PNG_1x1
    if ext == "wav":
        return _WAV_HEADER
    if ext == "srt":
        return _SRT_TEXT
    return b""


# ─── S3 client (separate from modal_app so the worker stays self-contained) ──


_s3 = None


def _s3_client():
    global _s3
    if _s3 is None:
        import boto3
        from botocore.client import Config

        kwargs: dict[str, Any] = {
            "region_name": os.environ.get("S3_REGION", "us-east-1"),
            "config": Config(signature_version="s3v4",
                             s3={"addressing_style": "path"}),
        }
        if os.environ.get("S3_ENDPOINT_URL"):
            kwargs["endpoint_url"] = os.environ["S3_ENDPOINT_URL"]
        if os.environ.get("AWS_ACCESS_KEY_ID"):
            kwargs["aws_access_key_id"] = os.environ["AWS_ACCESS_KEY_ID"]
            kwargs["aws_secret_access_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]
        _s3 = boto3.client("s3", **kwargs)
    return _s3


def _bucket() -> str:
    return os.environ.get("S3_BUCKET", "vidplatform")


def _upload(payload: bytes, key: str, content_type: str) -> int:
    try:
        _s3_client().put_object(
            Bucket=_bucket(), Key=key, Body=payload, ContentType=content_type,
        )
        return len(payload)
    except Exception as exc:
        logger.warning("[stub] S3 upload failed for %s: %s", key, exc)
        return 0


# ─── Key + hash helpers ────────────────────────────────────────────────


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _asset_key(
    *,
    project_id: str, asset_type: str, short_hash: str, extension: str,
    scene_index: int | str | None = None,
    language: str | None = None,
    character_id: str | None = None,
) -> str:
    base = f"projects/{project_id}"
    if asset_type == "thumbnail":
        return f"{base}/thumbnails/{scene_index}-{short_hash}.{extension}"
    if asset_type == "character_ref":
        return f"{base}/character_refs/{character_id}-{short_hash}.{extension}"
    if asset_type == "scene_video":
        return f"{base}/scene_videos/{scene_index}-{short_hash}.{extension}"
    if asset_type == "native_audio":
        return f"{base}/native_audio/{scene_index}-{short_hash}.{extension}"
    if asset_type == "voice":
        return f"{base}/voices/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "lipsync_video":
        return f"{base}/lipsync/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "subtitle_srt":
        return f"{base}/subtitles/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "composite":
        return f"{base}/composites/{language}/{scene_index}-{short_hash}.{extension}"
    if asset_type == "final_export":
        return f"{base}/exports/{language}/final-{short_hash}.{extension}"
    return f"{base}/{asset_type}/{short_hash}.{extension}"


def _scene_index_for(scene_id: str | None) -> int | None:
    if not scene_id:
        return None
    try:
        from sqlalchemy import text
        with db.session_scope() as s:
            row = s.execute(
                text("SELECT scene_index FROM scenes WHERE id = :sid"),
                {"sid": scene_id},
            ).fetchone()
            return int(row[0]) if row else None
    except Exception:
        return None


# ─── Public entrypoint ─────────────────────────────────────────────────


def materialise(fn_name: str, kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """Run the fixture-mode version of `fn_name`.

    Returns a dict shaped like the real Modal function's output (with a real
    `asset_id`) so the rest of the pipeline doesn't have to special-case stubs.

    Returns the plain `{"stub": True, ...}` shape for functions that don't
    produce assets (`ping`) or when required identifiers (project_id) are
    missing.
    """
    # musetalk only fires when has_speaker=True; mirror the real signature.
    if fn_name == "musetalk_sync" and not kwargs.get("has_speaker", True):
        return None

    if fn_name not in _ASSET_TYPE_BY_FN:
        return {"stub": True, "fn": fn_name, "kwargs": kwargs}

    project_id = kwargs.get("project_id")
    if not project_id:
        return {"stub": True, "fn": fn_name, "kwargs": kwargs}

    asset_type, ext, mime = _ASSET_TYPE_BY_FN[fn_name]
    scene_id = kwargs.get("scene_id")
    language = kwargs.get("language")
    character_id = kwargs.get("character_id")

    h = _content_hash({
        "stub_version": 1, "fn": fn_name,
        "project_id": str(project_id),
        "scene_id": str(scene_id) if scene_id else None,
        "language": language,
        "character_id": str(character_id) if character_id else None,
        "asset_type": asset_type,
    })

    scene_index = _scene_index_for(scene_id) if scene_id else None
    key = _asset_key(
        project_id=str(project_id), asset_type=asset_type,
        short_hash=h[:8], extension=ext,
        scene_index=scene_index, language=language,
        character_id=str(character_id) if character_id else None,
    )

    payload = _fixture_bytes(ext)
    byte_count = _upload(payload, key, mime) if payload else 0

    try:
        asset_id = db.register_asset(
            project_id=str(project_id),
            scene_id=str(scene_id) if scene_id else None,
            asset_type=asset_type, language=language,
            storage_key=key, content_hash=h,
            mime_type=mime, bytes_=byte_count,
            metadata={"stub": True, "fn": fn_name},
        )
    except Exception as exc:
        logger.warning("[stub] register_asset failed for %s: %s", fn_name, exc)
        asset_id = str(uuid.uuid4())

    logger.info("[stub] materialised %s → asset %s (%s)", fn_name, asset_id, key)
    return {
        "asset_id": asset_id,
        "storage_key": key,
        "asset_type": asset_type,
        "scene_id": str(scene_id) if scene_id else None,
        "language": language,
        "content_hash": h,
        "stub": True,
        "fn": fn_name,
    }
