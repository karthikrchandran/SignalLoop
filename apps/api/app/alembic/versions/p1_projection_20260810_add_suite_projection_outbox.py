"""add durable suite projection outbox

Revision ID: p1_projection_20260810
Revises: p1_merge_20260810
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_projection_20260810"
down_revision: str | None = "p1_merge_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create immutable, retryable suite-to-product projection intents."""
    op.create_table(
        "suite_projection_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("projection_kind", sa.String(length=64), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledgement_receipt", sa.JSON(), nullable=True),
        sa.Column("dead_letter_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint(
            "installation_id",
            "projection_kind",
            "projection_version",
            name="uq_suite_projection_installation_kind_version",
        ),
    )
    op.create_index("ix_suite_projection_outbox_event_id", "suite_projection_outbox", ["event_id"])
    op.create_index("ix_suite_projection_outbox_tenant_id", "suite_projection_outbox", ["tenant_id"])
    op.create_index("ix_suite_projection_outbox_installation_id", "suite_projection_outbox", ["installation_id"])
    op.create_index("ix_suite_projection_outbox_status", "suite_projection_outbox", ["status"])
    op.create_index(
        "ix_suite_projection_outbox_status_next_attempt",
        "suite_projection_outbox",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    """Drop the projection outbox."""
    op.drop_index("ix_suite_projection_outbox_status_next_attempt", table_name="suite_projection_outbox")
    op.drop_index("ix_suite_projection_outbox_status", table_name="suite_projection_outbox")
    op.drop_index("ix_suite_projection_outbox_installation_id", table_name="suite_projection_outbox")
    op.drop_index("ix_suite_projection_outbox_tenant_id", table_name="suite_projection_outbox")
    op.drop_index("ix_suite_projection_outbox_event_id", table_name="suite_projection_outbox")
    op.drop_table("suite_projection_outbox")
