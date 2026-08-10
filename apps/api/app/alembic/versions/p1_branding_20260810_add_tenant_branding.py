"""add immutable tenant branding versions and assets."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_branding_20260810"
down_revision: str | None = "p1_install_20260809"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_branding_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("product_name", sa.String(80), nullable=True),
        sa.Column("headline", sa.String(120), nullable=False),
        sa.Column("supporting_copy", sa.String(300), nullable=False),
        sa.Column("primary_color", sa.String(7), nullable=False),
        sa.Column("secondary_color", sa.String(7), nullable=False),
        sa.Column("support_url", sa.String(2048), nullable=True),
        sa.Column("privacy_url", sa.String(2048), nullable=True),
        sa.Column("legal_url", sa.String(2048), nullable=True),
        sa.Column("logo_asset_id", sa.Uuid(), nullable=True),
        sa.Column("hero_asset_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("validated_by", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "version", name="uq_branding_tenant_version"),
    )
    op.create_index("ix_tenant_branding_version_tenant_id", "tenant_branding_version", ["tenant_id"])
    op.create_index("ix_tenant_branding_version_lifecycle", "tenant_branding_version", ["lifecycle"])
    op.create_table(
        "tenant_brand_asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_brand_asset_tenant_id", "tenant_brand_asset", ["tenant_id"])
    op.create_index("ix_tenant_brand_asset_sha256", "tenant_brand_asset", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_tenant_brand_asset_sha256", table_name="tenant_brand_asset")
    op.drop_index("ix_tenant_brand_asset_tenant_id", table_name="tenant_brand_asset")
    op.drop_table("tenant_brand_asset")
    op.drop_index("ix_tenant_branding_version_lifecycle", table_name="tenant_branding_version")
    op.drop_index("ix_tenant_branding_version_tenant_id", table_name="tenant_branding_version")
    op.drop_table("tenant_branding_version")
