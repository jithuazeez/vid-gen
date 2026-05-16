"""Scene Engine output — Timeline + Characters.

Mirrors architecture.md §19 (scene_engine_system.md output schema).
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.brief import Language

SubtitlePosition = Literal["auto", "top", "bottom", "custom"]


class CharacterPlan(BaseModel):
    name: str
    description: str = Field(description="Detailed visual description for SDXL-Turbo")


class ScenePlan(BaseModel):
    scene_index: int = Field(ge=1)
    duration_seconds: float = Field(ge=2.0, le=15.0)
    visual_prompt: str = Field(min_length=10)
    narration_script: str = Field(min_length=1)
    has_speaker: bool = False
    character_names: list[str] = Field(default_factory=list)
    subtitle_position: SubtitlePosition = "auto"


class Timeline(BaseModel):
    primary_language: Language
    scenes: list[ScenePlan] = Field(min_length=1)
    characters: list[CharacterPlan] = Field(default_factory=list)
