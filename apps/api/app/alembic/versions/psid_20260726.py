"""add platform shared lead and order identities

Revision ID: psid_20260726
Revises: 20260708_add_platform_shared_record_metadata
Create Date: 2026-07-26 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "psid_20260726"
down_revision: str | None = "20260708_add_platform_shared_record_metadata"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_shared_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("external_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("data_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "entity_type",
            "external_key",
            name="uq_platform_shared_identities_workspace_type_key",
        ),
    )
    op.create_index(
        "ix_platform_shared_identities_workspace_id",
        "platform_shared_identities",
        ["workspace_id"],
    )
    op.create_index(
        "ix_platform_shared_identities_entity_type",
        "platform_shared_identities",
        ["entity_type"],
    )
    op.create_index(
        "ix_platform_shared_identities_external_key",
        "platform_shared_identities",
        ["external_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_shared_identities_external_key", table_name="platform_shared_identities")
    op.drop_index("ix_platform_shared_identities_entity_type", table_name="platform_shared_identities")
    op.drop_index("ix_platform_shared_identities_workspace_id", table_name="platform_shared_identities")
    op.drop_table("platform_shared_identities")
