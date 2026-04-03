"""Add campaign intake tables

Revision ID: b7c1012f3a44
Revises: 7b9a6c2e11f4
Create Date: 2026-03-30 19:30:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


# revision identifiers, used by Alembic.
revision = "b7c1012f3a44"
down_revision = "7b9a6c2e11f4"
branch_labels = None
depends_on = None


campaign_status_enum = postgresql.ENUM(
    "draft",
    "active",
    "paused",
    "pending_approval",
    name="campaignstatus",
    create_type=False,
)
segment_operator_enum = postgresql.ENUM(
    "equals",
    "contains",
    "in-list",
    "startsWith",
    name="segmentoperator",
    create_type=False,
)


def upgrade() -> None:
    campaign_status_enum.create(op.get_bind(), checkfirst=True)
    segment_operator_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", campaign_status_enum, nullable=False, server_default="draft"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaigns_workspace_id"), "campaigns", ["workspace_id"], unique=False)

    op.create_table(
        "campaign_contact_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mapping_json", sa.JSON(), nullable=False),
        sa.Column("headers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaign_contact_imports_campaign_id"),
        "campaign_contact_imports",
        ["campaign_id"],
        unique=False,
    )

    op.create_table(
        "campaign_contact_staging",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mapped_data_json", sa.JSON(), nullable=False),
        sa.Column("error_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["campaign_contact_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaign_contact_staging_campaign_id"),
        "campaign_contact_staging",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_contact_staging_import_id"),
        "campaign_contact_staging",
        ["import_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_contact_staging_workspace_id"),
        "campaign_contact_staging",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "campaign_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("estimated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaign_segments_campaign_id"), "campaign_segments", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_campaign_segments_workspace_id"), "campaign_segments", ["workspace_id"], unique=False)

    op.create_table(
        "campaign_segment_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("operator", segment_operator_enum, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expression_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["segment_id"], ["campaign_segments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaign_segment_rules_segment_id"),
        "campaign_segment_rules",
        ["segment_id"],
        unique=False,
    )

    op.create_table(
        "campaign_channel_strategy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("offer_pack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("offer_pack_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("strategy_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaign_channel_strategy_campaign_id"),
        "campaign_channel_strategy",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_channel_strategy_workspace_id"),
        "campaign_channel_strategy",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_campaign_channel_strategy_workspace_id"), table_name="campaign_channel_strategy")
    op.drop_index(op.f("ix_campaign_channel_strategy_campaign_id"), table_name="campaign_channel_strategy")
    op.drop_table("campaign_channel_strategy")

    op.drop_index(op.f("ix_campaign_segment_rules_segment_id"), table_name="campaign_segment_rules")
    op.drop_table("campaign_segment_rules")

    op.drop_index(op.f("ix_campaign_segments_workspace_id"), table_name="campaign_segments")
    op.drop_index(op.f("ix_campaign_segments_campaign_id"), table_name="campaign_segments")
    op.drop_table("campaign_segments")

    op.drop_index(op.f("ix_campaign_contact_staging_workspace_id"), table_name="campaign_contact_staging")
    op.drop_index(op.f("ix_campaign_contact_staging_import_id"), table_name="campaign_contact_staging")
    op.drop_index(op.f("ix_campaign_contact_staging_campaign_id"), table_name="campaign_contact_staging")
    op.drop_table("campaign_contact_staging")

    op.drop_index(op.f("ix_campaign_contact_imports_campaign_id"), table_name="campaign_contact_imports")
    op.drop_table("campaign_contact_imports")

    op.drop_index(op.f("ix_campaigns_workspace_id"), table_name="campaigns")
    op.drop_table("campaigns")

    segment_operator_enum.drop(op.get_bind(), checkfirst=True)
    campaign_status_enum.drop(op.get_bind(), checkfirst=True)
