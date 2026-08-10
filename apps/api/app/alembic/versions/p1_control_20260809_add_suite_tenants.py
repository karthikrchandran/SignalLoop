"""add suite tenants, entitlements, and invitations"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_control_20260809"
down_revision: str | None = "p1_session_20260809"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "suite_tenant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_suite_tenant_key", "suite_tenant", ["key"])
    op.create_table(
        "suite_tenant_entitlement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "product_code", name="uq_suite_entitlement_tenant_product"),
    )
    op.create_index("ix_suite_tenant_entitlement_tenant_id", "suite_tenant_entitlement", ["tenant_id"])
    op.create_table(
        "suite_tenant_invitation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_suite_tenant_invitation_tenant_id", "suite_tenant_invitation", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_suite_tenant_invitation_tenant_id", table_name="suite_tenant_invitation")
    op.drop_table("suite_tenant_invitation")
    op.drop_index("ix_suite_tenant_entitlement_tenant_id", table_name="suite_tenant_entitlement")
    op.drop_table("suite_tenant_entitlement")
    op.drop_index("ix_suite_tenant_key", table_name="suite_tenant")
    op.drop_table("suite_tenant")
