"""add_scheduling_request_fields

Revision ID: x1y2z3a4b5c6
Revises: w8l9m0n1o2p3
Create Date: 2026-07-08 00:00:00.000000

Extends the existing ``scheduling_requests`` table with:
  - source          VARCHAR(32)  — how the request was triggered
  - meeting_link    TEXT         — Calendly link sent to contact
  - calendly_event_id VARCHAR(255) — Calendly event URI from webhook
  - meeting_datetime TIMESTAMPTZ — confirmed booking time
  - assigned_to_email VARCHAR(255) — rep who will take the meeting
  - notes           TEXT
  - updated_at      TIMESTAMPTZ
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "x1y2z3a4b5c6"
down_revision: str | None = "w8l9m0n1o2p3"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply migration."""
    op.add_column(
        "scheduling_requests",
        sa.Column("source", sa.String(32), nullable=False, server_default="voice_call"),
    )
    op.add_column(
        "scheduling_requests",
        sa.Column("meeting_link", sa.Text(), nullable=True),
    )
    op.add_column(
        "scheduling_requests",
        sa.Column("calendly_event_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "scheduling_requests",
        sa.Column("meeting_datetime", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduling_requests",
        sa.Column("assigned_to_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "scheduling_requests",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "scheduling_requests",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_sched_updated", "scheduling_requests", ["updated_at"])
    op.create_index("idx_sched_campaign", "scheduling_requests", ["campaign_id"])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index("idx_sched_campaign", "scheduling_requests")
    op.drop_index("idx_sched_updated", "scheduling_requests")
    op.drop_column("scheduling_requests", "updated_at")
    op.drop_column("scheduling_requests", "notes")
    op.drop_column("scheduling_requests", "assigned_to_email")
    op.drop_column("scheduling_requests", "meeting_datetime")
    op.drop_column("scheduling_requests", "calendly_event_id")
    op.drop_column("scheduling_requests", "meeting_link")
    op.drop_column("scheduling_requests", "source")
