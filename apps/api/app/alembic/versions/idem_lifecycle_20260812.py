"""add durable idempotency lifecycle fields

Revision ID: idem_lifecycle_20260812
Revises: idem_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "idem_lifecycle_20260812"
down_revision = "idem_20260812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "idempotency_records",
        sa.Column("failure_reason", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "idempotency_records",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("idempotency_records", "lease_expires_at")
    op.drop_column("idempotency_records", "failure_reason")
