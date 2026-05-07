"""create_audit_events_table

Revision ID: f2a3b4c5d6e7
Revises: ab178426267c, a0b1c2d3e4f5
Create Date: 2026-05-02 00:00:00.000000

Adds:
  - audit_events append-only PostgreSQL table
  - JSONB payload column
  - database trigger preventing UPDATE and DELETE
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2a3b4c5d6e7"
down_revision: tuple[str, ...] = ("ab178426267c", "a0b1c2d3e4f5")
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_name", sa.String(255), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(128), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_event_type", "audit_events", ["event_name"])
    op.create_index("idx_audit_workspace", "audit_events", ["workspace_id"])
    op.create_index("idx_audit_created", "audit_events", ["created_at"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_events_update_delete()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_events_update_delete();
        """
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_events_update_delete()")
    op.drop_index("idx_audit_created", table_name="audit_events")
    op.drop_index("idx_audit_workspace", table_name="audit_events")
    op.drop_index("idx_audit_event_type", table_name="audit_events")
    op.drop_table("audit_events")
