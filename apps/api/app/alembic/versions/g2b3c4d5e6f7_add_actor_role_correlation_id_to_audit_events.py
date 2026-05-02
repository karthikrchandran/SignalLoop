"""add_actor_role_correlation_id_to_audit_events

Revision ID: g2b3c4d5e6f7
Revises: f2a3b4c5d6e7
Create Date: 2026-05-10 00:00:00.000000

Adds:
  - actor_role (VARCHAR 64, nullable) to audit_events
  - correlation_id (VARCHAR 255, nullable) to audit_events
  - composite index idx_audit_workspace_created (workspace_id, created_at)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "g2b3c4d5e6f7"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("actor_role", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "idx_audit_workspace_created",
        "audit_events",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_workspace_created", table_name="audit_events")
    op.drop_column("audit_events", "correlation_id")
    op.drop_column("audit_events", "actor_role")
