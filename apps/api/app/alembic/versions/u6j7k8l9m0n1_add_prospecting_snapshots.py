"""add prospecting snapshots

Revision ID: u6j7k8l9m0n1
Revises: eee6da01aff1
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "u6j7k8l9m0n1"
down_revision: str | tuple[str, ...] | None = "eee6da01aff1"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "prospecting_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("company_url", sa.Text(), nullable=True),
        sa.Column("sources_json", sa.JSON(), nullable=True),
        sa.Column("research_json", sa.JSON(), nullable=True),
        sa.Column("email_draft", sa.Text(), nullable=False),
        sa.Column("voice_opener", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prospecting_snapshots_workspace_id", "prospecting_snapshots", ["workspace_id"])
    op.create_index("ix_prospecting_snapshots_contact_id", "prospecting_snapshots", ["contact_id"])
    op.create_index("ix_prospecting_snapshots_created_by", "prospecting_snapshots", ["created_by"])
    op.create_index("ix_prospecting_snapshots_created_at", "prospecting_snapshots", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_prospecting_snapshots_created_at", table_name="prospecting_snapshots")
    op.drop_index("ix_prospecting_snapshots_created_by", table_name="prospecting_snapshots")
    op.drop_index("ix_prospecting_snapshots_contact_id", table_name="prospecting_snapshots")
    op.drop_index("ix_prospecting_snapshots_workspace_id", table_name="prospecting_snapshots")
    op.drop_table("prospecting_snapshots")
