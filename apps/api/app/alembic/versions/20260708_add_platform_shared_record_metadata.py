"""add platform shared record metadata

Revision ID: 20260708_add_platform_shared_record_metadata
Revises: 20260707_add_platform_shared_records
Create Date: 2026-07-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_add_platform_shared_record_metadata"
down_revision: str | tuple[str, ...] | None = "20260707_add_platform_shared_records"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "platform_shared_accounts",
        sa.Column("account_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "platform_shared_accounts",
        sa.Column("website_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "platform_shared_accounts",
        sa.Column("industry", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "platform_shared_accounts",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "platform_shared_accounts",
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    op.add_column(
        "platform_shared_contacts",
        sa.Column("company_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column("first_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column("last_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="UTC",
        ),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column("source_channel", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column("intent_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "platform_shared_contacts",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("platform_shared_contacts", "last_seen_at")
    op.drop_column("platform_shared_contacts", "intent_json")
    op.drop_column("platform_shared_contacts", "tags_json")
    op.drop_column("platform_shared_contacts", "source_channel")
    op.drop_column("platform_shared_contacts", "timezone")
    op.drop_column("platform_shared_contacts", "last_name")
    op.drop_column("platform_shared_contacts", "first_name")
    op.drop_column("platform_shared_contacts", "company_name")

    op.drop_column("platform_shared_accounts", "tags_json")
    op.drop_column("platform_shared_accounts", "summary")
    op.drop_column("platform_shared_accounts", "industry")
    op.drop_column("platform_shared_accounts", "website_url")
    op.drop_column("platform_shared_accounts", "account_key")
