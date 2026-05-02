"""add_post_call_processed_to_call_sessions

Revision ID: a0b1c2d3e4f5
Revises: f1a2b3c4d5e6
Create Date: 2026-05-02 00:00:00.000000

Adds:
  - post_call_processed (Boolean, default False, not null) to call_sessions
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "call_sessions",
        sa.Column(
            "post_call_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "idx_cs_post_call_processed",
        "call_sessions",
        ["post_call_processed"],
    )


def downgrade() -> None:
    op.drop_index("idx_cs_post_call_processed", "call_sessions")
    op.drop_column("call_sessions", "post_call_processed")
