"""initial schema — projects, scenes, characters, overlays, subtitles, assets, jobs, messages

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("brief", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("primary_language", sa.String(8)),
        sa.Column("active_language", sa.String(8)),
        sa.Column("available_languages", postgresql.ARRAY(sa.String(8)), nullable=False,
                  server_default=sa.text("'{}'::text[]")),
        sa.Column("aspect_ratio", sa.String(8)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("has_characters", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("music_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="42"),
    )
    op.create_index("projects_status_idx", "projects", ["status"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("conv_msgs_project_idx", "conversation_messages", ["project_id", "created_at"])

    op.create_table(
        "characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_image_asset_id", postgresql.UUID(as_uuid=True)),
    )

    op.create_table(
        "scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_index", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(5, 2), nullable=False),
        sa.Column("visual_prompt", sa.Text(), nullable=False),
        sa.Column("narration_script", sa.Text(), nullable=False),
        sa.Column("has_speaker", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("character_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False,
                  server_default=sa.text("'{}'::uuid[]")),
        sa.Column("subtitle_position", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("subtitle_custom_y", sa.Numeric(4, 3)),
        sa.Column("thumbnail_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("scene_video_asset_id", postgresql.UUID(as_uuid=True)),
        sa.UniqueConstraint("project_id", "scene_index", name="uq_scene_project_index"),
    )
    op.create_index("scenes_project_idx", "scenes", ["project_id", "scene_index"])

    op.create_table(
        "overlays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overlay_type", sa.String(32), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("start_seconds", sa.Numeric(6, 2), nullable=False),
        sa.Column("end_seconds", sa.Numeric(6, 2), nullable=False),
        sa.Column("position", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("animation", sa.String(32), nullable=False, server_default="fade"),
        sa.Column("style", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "subtitles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("cues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_position", sa.String(16)),
        sa.UniqueConstraint("scene_id", "language", name="uq_subtitle_scene_lang"),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("scenes.id", ondelete="CASCADE")),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("language", sa.String(8)),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("bytes", sa.BigInteger()),
        sa.Column("mime_type", sa.String(64)),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("assets_content_hash_idx", "assets", ["content_hash"], unique=True)
    op.create_index("assets_lookup_idx", "assets",
                    ["project_id", "scene_id", "asset_type", "language"])

    op.create_table(
        "render_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("language", sa.String(8)),
        sa.Column("scene_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.String(64)),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("modal_call_ids", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error", sa.Text()),
        sa.Column("idempotency_key", sa.String(255), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("jobs_status_idx", "render_jobs", ["status"])
    op.create_index("jobs_project_idx", "render_jobs", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_table("render_jobs")
    op.drop_table("assets")
    op.drop_table("subtitles")
    op.drop_table("overlays")
    op.drop_table("scenes")
    op.drop_table("characters")
    op.drop_table("conversation_messages")
    op.drop_table("projects")
