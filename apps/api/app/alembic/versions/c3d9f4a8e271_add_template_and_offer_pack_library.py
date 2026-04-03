"""Add template and offer-pack library tables

Revision ID: c3d9f4a8e271
Revises: b7c1012f3a44
Create Date: 2026-03-30 21:10:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


# revision identifiers, used by Alembic.
revision = "c3d9f4a8e271"
down_revision = "b7c1012f3a44"
branch_labels = None
depends_on = None


template_status_enum = postgresql.ENUM(
    "draft",
    "published",
    "archived",
    name="templatestatus",
    create_type=False,
)


def upgrade() -> None:
    template_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_templates_workspace_id"), "templates", ["workspace_id"], unique=False)

    op.create_table(
        "template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", template_status_enum, nullable=False, server_default="draft"),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("guardrail_compliant", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("guardrail_report_json", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version_number", name="uq_template_version_number"),
    )
    op.create_index(op.f("ix_template_versions_template_id"), "template_versions", ["template_id"], unique=False)
    op.create_index(op.f("ix_template_versions_workspace_id"), "template_versions", ["workspace_id"], unique=False)
    op.create_index(
        "ix_template_versions_workspace_id_status",
        "template_versions",
        ["workspace_id", "status"],
        unique=False,
    )

    op.create_table(
        "template_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source_field", sa.String(length=100), nullable=False),
        sa.Column("default_value", sa.String(length=255), nullable=True),
        sa.Column("fallback_behavior", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "name", name="uq_template_token_name"),
    )
    op.create_index(op.f("ix_template_tokens_template_id"), "template_tokens", ["template_id"], unique=False)

    op.create_table(
        "offer_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offer_packs_workspace_id"), "offer_packs", ["workspace_id"], unique=False)

    op.create_table(
        "offer_pack_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", template_status_enum, nullable=False, server_default="draft"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("guardrail_compliant", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["offer_pack_id"], ["offer_packs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("offer_pack_id", "version_number", name="uq_offer_pack_version_number"),
    )
    op.create_index(op.f("ix_offer_pack_versions_offer_pack_id"), "offer_pack_versions", ["offer_pack_id"], unique=False)
    op.create_index(op.f("ix_offer_pack_versions_workspace_id"), "offer_pack_versions", ["workspace_id"], unique=False)
    op.create_index(
        "ix_offer_pack_versions_workspace_id_status",
        "offer_pack_versions",
        ["workspace_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_offer_pack_versions_default_per_offer_pack",
        "offer_pack_versions",
        ["offer_pack_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND status = 'published'"),
    )

    op.create_table(
        "offer_pack_template_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_pack_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("script_variant", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["offer_pack_version_id"], ["offer_pack_versions.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["template_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_offer_pack_template_bindings_offer_pack_version_id"),
        "offer_pack_template_bindings",
        ["offer_pack_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_offer_pack_template_bindings_template_version_id"),
        "offer_pack_template_bindings",
        ["template_version_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_campaign_channel_strategy_offer_pack_id",
        "campaign_channel_strategy",
        "offer_packs",
        ["offer_pack_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_campaign_channel_strategy_offer_pack_version_id",
        "campaign_channel_strategy",
        "offer_pack_versions",
        ["offer_pack_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_campaign_channel_strategy_offer_pack_version_id",
        "campaign_channel_strategy",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_campaign_channel_strategy_offer_pack_id",
        "campaign_channel_strategy",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_offer_pack_template_bindings_template_version_id"),
        table_name="offer_pack_template_bindings",
    )
    op.drop_index(
        op.f("ix_offer_pack_template_bindings_offer_pack_version_id"),
        table_name="offer_pack_template_bindings",
    )
    op.drop_table("offer_pack_template_bindings")

    op.drop_index("ix_offer_pack_versions_default_per_offer_pack", table_name="offer_pack_versions")
    op.drop_index("ix_offer_pack_versions_workspace_id_status", table_name="offer_pack_versions")
    op.drop_index(op.f("ix_offer_pack_versions_workspace_id"), table_name="offer_pack_versions")
    op.drop_index(op.f("ix_offer_pack_versions_offer_pack_id"), table_name="offer_pack_versions")
    op.drop_table("offer_pack_versions")

    op.drop_index(op.f("ix_offer_packs_workspace_id"), table_name="offer_packs")
    op.drop_table("offer_packs")

    op.drop_index(op.f("ix_template_tokens_template_id"), table_name="template_tokens")
    op.drop_table("template_tokens")

    op.drop_index("ix_template_versions_workspace_id_status", table_name="template_versions")
    op.drop_index(op.f("ix_template_versions_workspace_id"), table_name="template_versions")
    op.drop_index(op.f("ix_template_versions_template_id"), table_name="template_versions")
    op.drop_table("template_versions")

    op.drop_index(op.f("ix_templates_workspace_id"), table_name="templates")
    op.drop_table("templates")

    template_status_enum.drop(op.get_bind(), checkfirst=True)
