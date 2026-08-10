"""add suite memberships, product installations, and support grants"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p2_control_20260810"
down_revision: str | None = "p1_control_20260809"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "suite_membership",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_suite_membership_tenant_user"),
    )
    op.create_index("ix_suite_membership_tenant_id", "suite_membership", ["tenant_id"])
    op.create_index("ix_suite_membership_user_id", "suite_membership", ["user_id"])
    op.create_index("ix_suite_membership_status", "suite_membership", ["status"])

    op.create_table(
        "suite_role_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("role_bundle", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["suite_membership.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", "role_bundle", name="uq_suite_role_assignment_membership_bundle"),
    )
    op.create_index("ix_suite_role_assignment_membership_id", "suite_role_assignment", ["membership_id"])
    op.create_index("ix_suite_role_assignment_status", "suite_role_assignment", ["status"])

    op.create_table(
        "suite_product_installation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("local_identifier", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "product_code", name="uq_suite_installation_tenant_product"),
    )
    op.create_index("ix_suite_product_installation_tenant_id", "suite_product_installation", ["tenant_id"])
    op.create_index("ix_suite_product_installation_status", "suite_product_installation", ["status"])

    op.create_table(
        "suite_support_access_grant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("operator_user_id", sa.Uuid(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("ticket_reference", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suite_support_access_grant_tenant_id", "suite_support_access_grant", ["tenant_id"])
    op.create_index("ix_suite_support_access_grant_operator_user_id", "suite_support_access_grant", ["operator_user_id"])


def downgrade() -> None:
    op.drop_index("ix_suite_support_access_grant_operator_user_id", table_name="suite_support_access_grant")
    op.drop_index("ix_suite_support_access_grant_tenant_id", table_name="suite_support_access_grant")
    op.drop_table("suite_support_access_grant")
    op.drop_index("ix_suite_product_installation_status", table_name="suite_product_installation")
    op.drop_index("ix_suite_product_installation_tenant_id", table_name="suite_product_installation")
    op.drop_table("suite_product_installation")
    op.drop_index("ix_suite_role_assignment_status", table_name="suite_role_assignment")
    op.drop_index("ix_suite_role_assignment_membership_id", table_name="suite_role_assignment")
    op.drop_table("suite_role_assignment")
    op.drop_index("ix_suite_membership_status", table_name="suite_membership")
    op.drop_index("ix_suite_membership_user_id", table_name="suite_membership")
    op.drop_index("ix_suite_membership_tenant_id", table_name="suite_membership")
    op.drop_table("suite_membership")
