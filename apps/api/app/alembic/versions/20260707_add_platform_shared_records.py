"""add platform shared records

Revision ID: 20260707_add_platform_shared_records
Revises: vlen_20260726
Create Date: 2026-07-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260707_add_platform_shared_records"
down_revision: str | tuple[str, ...] | None = "vlen_20260726"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_shared_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("external_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_platform_shared_accounts_workspace_id_id",
        ),
    )
    op.create_index(
        "ix_platform_shared_accounts_workspace_id",
        "platform_shared_accounts",
        ["workspace_id"],
    )
    op.create_index(
        "ix_platform_shared_accounts_external_key",
        "platform_shared_accounts",
        ["external_key"],
        unique=True,
    )

    op.create_table(
        "platform_shared_contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("external_key", sa.String(length=255), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "parent_account_id"],
            ["platform_shared_accounts.workspace_id", "platform_shared_accounts.id"],
            name="fk_platform_shared_contacts_workspace_parent_account",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_shared_contacts_workspace_id",
        "platform_shared_contacts",
        ["workspace_id"],
    )
    op.create_index(
        "ix_platform_shared_contacts_external_key",
        "platform_shared_contacts",
        ["external_key"],
        unique=True,
    )
    op.create_index(
        "ix_platform_shared_contacts_email",
        "platform_shared_contacts",
        ["email"],
    )

    op.create_table(
        "platform_external_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_app", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "entity_type",
            "source_app",
            "source_record_id",
            name="uq_platform_external_links_source_identity",
        ),
    )
    op.create_index(
        "ix_platform_external_links_entity_type",
        "platform_external_links",
        ["entity_type"],
    )
    op.create_index(
        "ix_platform_external_links_entity_id",
        "platform_external_links",
        ["entity_id"],
    )
    op.create_index(
        "ix_platform_external_links_source_app",
        "platform_external_links",
        ["source_app"],
    )
    op.create_index(
        "ix_platform_external_links_source_record_id",
        "platform_external_links",
        ["source_record_id"],
    )
    op.create_index(
        "ix_platform_external_links_workspace_id",
        "platform_external_links",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_external_links_workspace_id",
        table_name="platform_external_links",
    )
    op.drop_index(
        "ix_platform_external_links_source_record_id",
        table_name="platform_external_links",
    )
    op.drop_index(
        "ix_platform_external_links_source_app",
        table_name="platform_external_links",
    )
    op.drop_index(
        "ix_platform_external_links_entity_id",
        table_name="platform_external_links",
    )
    op.drop_index(
        "ix_platform_external_links_entity_type",
        table_name="platform_external_links",
    )
    op.drop_table("platform_external_links")

    op.drop_index(
        "ix_platform_shared_contacts_email",
        table_name="platform_shared_contacts",
    )
    op.drop_index(
        "ix_platform_shared_contacts_external_key",
        table_name="platform_shared_contacts",
    )
    op.drop_index(
        "ix_platform_shared_contacts_workspace_id",
        table_name="platform_shared_contacts",
    )
    op.drop_table("platform_shared_contacts")

    op.drop_index(
        "ix_platform_shared_accounts_external_key",
        table_name="platform_shared_accounts",
    )
    op.drop_index(
        "ix_platform_shared_accounts_workspace_id",
        table_name="platform_shared_accounts",
    )
    op.drop_table("platform_shared_accounts")
