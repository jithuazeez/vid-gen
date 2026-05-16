"""Brief schema — slot-fill output from the chat orchestrator.

Mirrors architecture.md §9 ("Slot schema collected during chat").
"""
from typing import Literal

from pydantic import BaseModel, Field

VideoType = Literal["explainer", "cinematic", "social_reel", "ad"]
VideoStyle = Literal["realistic", "animated", "documentary", "minimalist"]
Language = Literal["en", "hi", "mr", "ta", "pa"]
NarrationTone = Literal["energetic", "calm", "authoritative", "friendly"]
AspectRatio = Literal["16:9", "9:16", "1:1"]


class Brief(BaseModel):
    """Complete brief once all slots are filled."""

    video_type: VideoType | None = None
    visual_style: VideoStyle | None = None
    duration_seconds: int | None = Field(default=None, ge=5, le=180)
    primary_language: Language | None = None
    narration_tone: NarrationTone | None = None
    has_characters: bool | None = None
    music_enabled: bool | None = None
    subtitles_enabled: bool | None = None
    aspect_ratio: AspectRatio | None = None
    topic: str | None = None

    REQUIRED_SLOTS: tuple[str, ...] = (  # type: ignore[assignment]
        "video_type",
        "visual_style",
        "duration_seconds",
        "primary_language",
        "narration_tone",
        "has_characters",
        "music_enabled",
        "subtitles_enabled",
        "aspect_ratio",
        "topic",
    )

    def is_complete(self) -> bool:
        return all(getattr(self, k) is not None for k in self.REQUIRED_SLOTS)

    def missing(self) -> list[str]:
        return [k for k in self.REQUIRED_SLOTS if getattr(self, k) is None]


class SlotUpdate(BaseModel):
    """Partial slot update emitted by the orchestrator on each turn."""

    video_type: VideoType | None = None
    visual_style: VideoStyle | None = None
    duration_seconds: int | None = None
    primary_language: Language | None = None
    narration_tone: NarrationTone | None = None
    has_characters: bool | None = None
    music_enabled: bool | None = None
    subtitles_enabled: bool | None = None
    aspect_ratio: AspectRatio | None = None
    topic: str | None = None
