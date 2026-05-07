"""add_dead_letter_events

Revision ID: c1d2e3f4a5b6
Revises: ab178426267c
Create Date: 2026-05-02 00:00:00.000000

Adds:
  - failure_reason (Text, nullable) on action_queue
  - dead_lettered_at (DateTime tz, nullable) on action_queue
  - dead_letter_events table (Story 5.3 – NFR8 SLA enforcement)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "ab178426267c"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # action_queue — new columns for dead-letter state
    # ------------------------------------------------------------------
    """Apply this Alembic migration."""
    op.add_column(
        "action_queue",
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "action_queue",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # dead_letter_events
    # ------------------------------------------------------------------
    op.create_table(
        "dead_letter_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_queue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False, server_default="dead_lettered"),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["action_queue_id"], ["action_queue.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dle_campaign_id", "dead_letter_events", ["campaign_id"])
    op.create_index("idx_dle_action_queue_id", "dead_letter_events", ["action_queue_id"])


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_index("idx_dle_action_queue_id", table_name="dead_letter_events")
    op.drop_index("idx_dle_campaign_id", table_name="dead_letter_events")
    op.drop_table("dead_letter_events")
    op.drop_column("action_queue", "dead_lettered_at")
    op.drop_column("action_queue", "failure_reason")
