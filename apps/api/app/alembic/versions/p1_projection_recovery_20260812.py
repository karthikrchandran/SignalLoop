"""add projection dispatch leasing and retry schedule"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_projection_recovery_20260812"
down_revision: str | None = "p1_projection_20260812"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "projection_dispatch_event",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "projection_dispatch_event", sa.Column("lease_token", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "projection_dispatch_event",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_projection_dispatch_event_available_at",
        "projection_dispatch_event",
        ["available_at"],
    )
    op.create_index(
        "ix_projection_dispatch_event_lease_token",
        "projection_dispatch_event",
        ["lease_token"],
    )
    op.create_index(
        "ix_projection_dispatch_event_lease_expires_at",
        "projection_dispatch_event",
        ["lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_projection_dispatch_event_lease_expires_at", table_name="projection_dispatch_event")
    op.drop_index("ix_projection_dispatch_event_lease_token", table_name="projection_dispatch_event")
    op.drop_index("ix_projection_dispatch_event_available_at", table_name="projection_dispatch_event")
    op.drop_column("projection_dispatch_event", "lease_expires_at")
    op.drop_column("projection_dispatch_event", "lease_token")
    op.drop_column("projection_dispatch_event", "available_at")
