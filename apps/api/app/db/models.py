"""SQLAlchemy models — mirrors architecture.md §6.

Schema is the source of truth; keep these in lockstep with the Alembic migration.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    # draft | collecting | planning | rendering | ready | completed | failed | cancelled

    brief: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    primary_language: Mapped[str | None] = mapped_column(String(8))
    active_language: Mapped[str | None] = mapped_column(String(8))
    available_languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(8)), nullable=False, default=list
    )
    aspect_ratio: Mapped[str | None] = mapped_column(String(8))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    has_characters: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    music_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)

    scenes: Mapped[list[Scene]] = relationship(back_populates="project", cascade="all, delete-orphan")
    characters: Mapped[list[Character]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    overlays: Mapped[list[Overlay]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    assets: Mapped[list[Asset]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[RenderJob]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="messages")

    __table_args__ = (Index("conv_msgs_project_idx", "project_id", "created_at"),)


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference_image_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    project: Mapped[Project] = relationship(back_populates="characters")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    visual_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    narration_script: Mapped[str] = mapped_column(Text, nullable=False)
    has_speaker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    character_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    subtitle_position: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    subtitle_custom_y: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    thumbnail_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    scene_video_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    project: Mapped[Project] = relationship(back_populates="scenes")

    __table_args__ = (
        UniqueConstraint("project_id", "scene_index", name="uq_scene_project_index"),
        Index("scenes_project_idx", "project_id", "scene_index"),
    )


class Overlay(Base):
    __tablename__ = "overlays"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    overlay_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    start_seconds: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    end_seconds: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    position: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    animation: Mapped[str] = mapped_column(String(32), nullable=False, default="fade")
    style: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped[Project] = relationship(back_populates="overlays")


class Subtitle(Base):
    __tablename__ = "subtitles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenes.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    cues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    generated_position: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (UniqueConstraint("scene_id", "language", name="uq_subtitle_scene_lang"),)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenes.id", ondelete="CASCADE"),
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # thumbnail | character_ref | scene_video | voice | lipsync_video |
    # subtitle_srt | music | composite | final_export
    language: Mapped[str | None] = mapped_column(String(8))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(64))
    asset_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="assets")

    __table_args__ = (
        Index("assets_content_hash_idx", "content_hash", unique=True),
        Index("assets_lookup_idx", "project_id", "scene_id", "asset_type", "language"),
    )


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # storyboard | initial_render | language_render | scene_regen | export
    language: Mapped[str | None] = mapped_column(String(8))
    scene_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    # pending | running | succeeded | failed | cancelled
    current_stage: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    modal_call_ids: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="jobs")

    __table_args__ = (Index("jobs_project_idx", "project_id", "created_at"),)
