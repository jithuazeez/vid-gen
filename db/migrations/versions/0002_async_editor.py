"""async editor — per-asset status/progress + subtitle source

Revision ID: 0002_async_editor
Revises: 0001_initial
Create Date: 2026-05-17

Adds the per-asset state machine that drives the async editor screen:
- assets.status / progress / updated_at — let the timeline render
  per-asset queued/generating/ready states without inferring from job rows
- subtitles.source — distinguishes script-derived estimated cues from
  whisper-aligned ones, so the editor can swap timings in place
- A unique index on (project_id, scene_id, asset_type, COALESCE(language,''))
  keeps the seeded slot rows idempotent.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_async_editor"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
    )
    op.add_column(
        "assets",
        sa.Column("progress", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "assets",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Existing rows were all "fully rendered" — defaults above cover them.
    # Drop server defaults so application code is the only writer going forward.
    op.alter_column("assets", "status", server_default=None)
    op.alter_column("assets", "progress", server_default=None)

    op.add_column(
        "subtitles",
        sa.Column("source", sa.String(16), nullable=False, server_default="whisper"),
    )
    op.alter_column("subtitles", "source", server_default=None)

    # Idempotency for the seeded asset slots. content_hash is empty for
    # queued rows, so we can't rely on the existing unique-on-content_hash
    # index. Use a partial unique on (project, scene, type, language) where
    # status is not 'ready' so we never block real cached assets.
    op.execute(
        """
        CREATE UNIQUE INDEX assets_slot_unique
        ON assets (project_id, COALESCE(scene_id, '00000000-0000-0000-0000-000000000000'),
                   asset_type, COALESCE(language, ''))
        WHERE status <> 'ready'
        """
    )

    # content_hash is required by the existing schema but we don't have one
    # for queued slots. Allow empty string sentinel.
    op.alter_column("assets", "content_hash", existing_type=sa.String(64), nullable=False)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS assets_slot_unique")
    op.drop_column("subtitles", "source")
    op.drop_column("assets", "updated_at")
    op.drop_column("assets", "progress")
    op.drop_column("assets", "status")
