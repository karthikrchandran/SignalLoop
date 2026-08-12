"""add durable HTTP mutation idempotency records

Revision ID: idem_20260812
Revises: tenant_20260809
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "idem_20260812"
down_revision = "tenant_20260809"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("response_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "operation", "idempotency_key", name="uq_idempotency_workspace_operation_key"),
    )
    op.create_index("ix_idempotency_records_workspace_id", "idempotency_records", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_workspace_id", table_name="idempotency_records")
    op.drop_table("idempotency_records")
