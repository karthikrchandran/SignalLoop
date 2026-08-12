"""add durable projection dispatch queue"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_projection_20260812"
down_revision: str | None = "p1_install_20260809"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "projection_dispatch_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "idempotency_key",
            name="uq_projection_dispatch_installation_idempotency",
        ),
    )
    op.create_index("ix_projection_dispatch_event_installation_id", "projection_dispatch_event", ["installation_id"])
    op.create_index("ix_projection_dispatch_event_tenant_id", "projection_dispatch_event", ["tenant_id"])
    op.create_index("ix_projection_dispatch_event_status", "projection_dispatch_event", ["status"])


def downgrade() -> None:
    op.drop_index("ix_projection_dispatch_event_status", table_name="projection_dispatch_event")
    op.drop_index("ix_projection_dispatch_event_tenant_id", table_name="projection_dispatch_event")
    op.drop_index("ix_projection_dispatch_event_installation_id", table_name="projection_dispatch_event")
    op.drop_table("projection_dispatch_event")
