"""add_runtime_config_and_worker_heartbeats

Revision ID: k6f7a8b9c0d1
Revises: j5e6f7a8b9c0
Create Date: 2026-05-28 00:00:00.000000

Adds:
  - workspace_runtime_configs for Deepgram, Groq, and team-notification overrides
  - worker_heartbeats for live worker liveness/error tracking
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "k6f7a8b9c0d1"
down_revision: str | tuple[str, ...] | None = "j5e6f7a8b9c0"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.create_table(
        "workspace_runtime_configs",
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("encrypted_deepgram_api_key", sa.Text(), nullable=True),
        sa.Column("encrypted_groq_api_key", sa.Text(), nullable=True),
        sa.Column("team_notification_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id"),
    )

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_key"),
    )
    op.create_index("ix_worker_heartbeats_last_seen_at", "worker_heartbeats", ["last_seen_at"])


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
    op.drop_table("workspace_runtime_configs")