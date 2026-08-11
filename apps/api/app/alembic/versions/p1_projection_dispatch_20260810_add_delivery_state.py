"""add projection delivery configuration and lease state

Revision ID: p1_projection_dispatch_20260810
Revises: p1_projection_20260810
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_projection_dispatch_20260810"
down_revision: str | None = "p1_projection_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Persist target configuration and crash-recovery lease state."""
    op.add_column(
        "suite_product_installation",
        sa.Column("projection_endpoint", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "suite_projection_outbox",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "suite_projection_outbox",
        sa.Column("last_error", sa.String(length=1000), nullable=True),
    )
    op.create_index(
        "ix_suite_projection_outbox_lease_expires_at",
        "suite_projection_outbox",
        ["lease_expires_at"],
    )


def downgrade() -> None:
    """Remove projection delivery lease state."""
    op.drop_index("ix_suite_projection_outbox_lease_expires_at", table_name="suite_projection_outbox")
    op.drop_column("suite_projection_outbox", "last_error")
    op.drop_column("suite_projection_outbox", "lease_expires_at")
    op.drop_column("suite_product_installation", "projection_endpoint")
