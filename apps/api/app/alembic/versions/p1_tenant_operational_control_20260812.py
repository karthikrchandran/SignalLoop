"""Add tenant-scoped, product-specific execution kill switches.

Revision ID: p1_tenant_operational_control_20260812
Revises: phase1_revenue_onboarding_merge_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_tenant_operational_control_20260812"
down_revision = "phase1_revenue_onboarding_merge_20260812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suite_tenant_operational_control",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paused_reason", sa.String(length=500), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "product_code", name="uq_suite_tenant_operational_control"
        ),
    )
    op.create_index(
        "ix_suite_tenant_operational_control_tenant_id",
        "suite_tenant_operational_control",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_suite_tenant_operational_control_tenant_id",
        table_name="suite_tenant_operational_control",
    )
    op.drop_table("suite_tenant_operational_control")
