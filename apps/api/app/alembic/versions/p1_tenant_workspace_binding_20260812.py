"""Bind SignalLoop workspaces to tenant product installations.

Revision ID: p1_tenant_workspace_binding_20260812
Revises: p1_tenant_operational_control_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_tenant_workspace_binding_20260812"
down_revision = "p1_tenant_operational_control_20260812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suite_tenant_workspace_binding",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id", name="uq_suite_workspace_binding_installation"),
        sa.UniqueConstraint("workspace_id", name="uq_suite_workspace_binding_workspace"),
        sa.UniqueConstraint("tenant_id", "workspace_id", name="uq_suite_workspace_binding_tenant_workspace"),
    )
    op.create_index(
        "ix_suite_tenant_workspace_binding_tenant_id",
        "suite_tenant_workspace_binding",
        ["tenant_id"],
    )
    op.create_index(
        "ix_suite_tenant_workspace_binding_installation_id",
        "suite_tenant_workspace_binding",
        ["installation_id"],
    )
    op.create_index(
        "ix_suite_tenant_workspace_binding_workspace_id",
        "suite_tenant_workspace_binding",
        ["workspace_id"],
    )
    op.create_index(
        "ix_suite_tenant_workspace_binding_status",
        "suite_tenant_workspace_binding",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_suite_tenant_workspace_binding_status", table_name="suite_tenant_workspace_binding")
    op.drop_index("ix_suite_tenant_workspace_binding_workspace_id", table_name="suite_tenant_workspace_binding")
    op.drop_index("ix_suite_tenant_workspace_binding_installation_id", table_name="suite_tenant_workspace_binding")
    op.drop_index("ix_suite_tenant_workspace_binding_tenant_id", table_name="suite_tenant_workspace_binding")
    op.drop_table("suite_tenant_workspace_binding")
