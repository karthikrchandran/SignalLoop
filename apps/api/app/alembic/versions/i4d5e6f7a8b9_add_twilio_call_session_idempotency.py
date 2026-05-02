"""add_twilio_call_session_idempotency

Revision ID: i4d5e6f7a8b9
Revises: h3c4d5e6f7a8, a0b1c2d3e4f5
Create Date: 2026-05-02 00:00:00.000000

Adds:
  - Twilio account/status tracking columns on call_sessions
  - unique call_request_id constraint for one CallSession per CallRequest
  - partial unique index for non-empty Twilio Call SID
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "i4d5e6f7a8b9"
down_revision: tuple[str, ...] = ("h3c4d5e6f7a8", "a0b1c2d3e4f5")
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "call_sessions",
        sa.Column("twilio_account_sid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "call_sessions",
        sa.Column("twilio_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "call_sessions",
        sa.Column("twilio_status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_cs_twilio_status", "call_sessions", ["twilio_status"])
    op.create_unique_constraint(
        "uq_call_sessions_call_request_id",
        "call_sessions",
        ["call_request_id"],
    )
    op.create_index(
        "uq_cs_twilio_call_sid_nonempty",
        "call_sessions",
        ["twilio_call_sid"],
        unique=True,
        postgresql_where=sa.text("twilio_call_sid <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_cs_twilio_call_sid_nonempty", table_name="call_sessions")
    op.drop_constraint("uq_call_sessions_call_request_id", "call_sessions", type_="unique")
    op.drop_index("idx_cs_twilio_status", table_name="call_sessions")
    op.drop_column("call_sessions", "twilio_status_updated_at")
    op.drop_column("call_sessions", "twilio_status")
    op.drop_column("call_sessions", "twilio_account_sid")
