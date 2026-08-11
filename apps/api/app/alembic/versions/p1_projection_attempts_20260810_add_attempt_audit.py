"""add immutable projection attempt audit

Revision ID: p1_projection_attempts_20260810
Revises: p1_projection_dispatch_20260810
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_projection_attempts_20260810"
down_revision: str | None = "p1_projection_dispatch_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Record every projection delivery decision immutably."""
    op.create_table(
        "suite_projection_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("projection_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=1000), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["projection_id"], ["suite_projection_outbox.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suite_projection_attempt_projection_id", "suite_projection_attempt", ["projection_id"])
    op.create_index("ix_suite_projection_attempt_outcome", "suite_projection_attempt", ["outcome"])


def downgrade() -> None:
    """Remove projection attempt audit records."""
    op.drop_index("ix_suite_projection_attempt_outcome", table_name="suite_projection_attempt")
    op.drop_index("ix_suite_projection_attempt_projection_id", table_name="suite_projection_attempt")
    op.drop_table("suite_projection_attempt")
