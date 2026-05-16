"""API DTOs for projects, scenes, overlays, jobs."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.brief import AspectRatio, Brief, Language

ProjectStatus = Literal[
    "draft", "collecting", "planning", "rendering", "ready", "completed", "failed", "cancelled"
]


class ProjectCreate(BaseModel):
    title: str | None = None


class ProjectPatch(BaseModel):
    title: str | None = None
    has_characters: bool | None = None
    music_enabled: bool | None = None
    active_language: Language | None = None
    brief: Brief | None = None


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scene_index: int
    duration_seconds: Decimal
    visual_prompt: str
    narration_script: str
    has_speaker: bool
    subtitle_position: str
    subtitle_custom_y: Decimal | None
    thumbnail_asset_id: uuid.UUID | None
    scene_video_asset_id: uuid.UUID | None
    character_ids: list[uuid.UUID] = Field(default_factory=list)


class OverlayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    overlay_type: str
    text: str | None
    start_seconds: Decimal
    end_seconds: Decimal
    position: dict[str, Any]
    animation: str
    style: dict[str, Any]


class SubtitleCue(BaseModel):
    start: float
    end: float
    text: str
    position: str | dict[str, float] | None = None


class SubtitleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scene_id: uuid.UUID
    language: str
    cues: list[SubtitleCue]
    generated_position: str | None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    job_type: str
    language: str | None
    status: str
    current_stage: str | None
    progress: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    status: ProjectStatus
    brief: dict[str, Any]
    primary_language: Language | None
    active_language: Language | None
    available_languages: list[Language]
    aspect_ratio: AspectRatio | None
    duration_seconds: int | None
    has_characters: bool
    music_enabled: bool
    created_at: datetime
    updated_at: datetime
    scenes: list[SceneOut] = Field(default_factory=list)
    overlays: list[OverlayOut] = Field(default_factory=list)
    latest_job: JobOut | None = None
