"""add_workspace_memberships

Revision ID: s4h5i6j7k8l9
Revises: r3g4h5i6j7k8
Create Date: 2026-06-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "s4h5i6j7k8l9"
down_revision: str | tuple[str, ...] | None = "r3g4h5i6j7k8"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

DEFAULT_WORKSPACE_ID = "default"
DEFAULT_WORKSPACE_NAME = "Default Workspace"

WORKSPACE_SOURCE_TABLES = (
    "campaigns",
    "contacts",
    "contact_state_history",
    "templates",
    "template_versions",
    "offer_packs",
    "offer_pack_versions",
    "provider_credentials",
    "workspace_runtime_configs",
    "workspace_provider_selections",
    "global_control_states",
    "governance_policies",
    "approval_requests",
    "audit_events",
    "kpi_daily_snapshots",
    "provider_event_logs",
    "chatbot_channel_configs",
    "chatbot_bot_configs",
    "chatbot_conversations",
    "chatbot_knowledge_sources",
    "chatbot_knowledge_chunks",
    "chatbot_messages",
    "chatbot_opt_outs",
    "chatbot_analytics_snapshots",
)


def _insert_ignore_prefix(bind) -> str:  # noqa: ANN001
    return "INSERT INTO" if bind.dialect.name == "postgresql" else "INSERT OR IGNORE INTO"


def _on_conflict_suffix(bind, constraint: str) -> str:  # noqa: ANN001
    if bind.dialect.name == "postgresql":
        return f" ON CONFLICT {constraint} DO NOTHING"
    return ""


def _uuid_expr(bind) -> str:  # noqa: ANN001
    if bind.dialect.name == "postgresql":
        return "uuid_generate_v4()"
    return "lower(hex(randomblob(16)))"


def _table_exists(bind, table_name: str) -> bool:  # noqa: ANN001
    return inspect(bind).has_table(table_name)


def _index_exists(bind, table_name: str, index_name: str) -> bool:  # noqa: ANN001
    if not _table_exists(bind, table_name):
        return False
    return any(index["name"] == index_name for index in inspect(bind).get_indexes(table_name))


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    if not _index_exists(bind, table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _insert_default_workspace(bind) -> None:  # noqa: ANN001
    prefix = _insert_ignore_prefix(bind)
    suffix = _on_conflict_suffix(bind, "(id)")
    bind.execute(
        sa.text(
            f"""
            {prefix} workspaces (id, display_name, created_at, updated_at)
            VALUES (:workspace_id, :display_name, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            {suffix}
            """
        ),
        {"workspace_id": DEFAULT_WORKSPACE_ID, "display_name": DEFAULT_WORKSPACE_NAME},
    )


def _backfill_workspaces(bind) -> None:  # noqa: ANN001
    prefix = _insert_ignore_prefix(bind)
    suffix = _on_conflict_suffix(bind, "(id)")
    for table_name in WORKSPACE_SOURCE_TABLES:
        if not _table_exists(bind, table_name):
            continue
        bind.execute(
            sa.text(
                f"""
                {prefix} workspaces (id, display_name, created_at, updated_at)
                SELECT DISTINCT workspace_id, workspace_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM {table_name}
                WHERE workspace_id IS NOT NULL AND workspace_id <> ''
                {suffix}
                """
            )
        )


def _backfill_default_user_memberships(bind) -> None:  # noqa: ANN001
    if not _table_exists(bind, "user"):
        return
    prefix = _insert_ignore_prefix(bind)
    suffix = _on_conflict_suffix(bind, "(workspace_id, user_id)")
    bind.execute(
        sa.text(
            f"""
            {prefix} workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at)
            SELECT
                {_uuid_expr(bind)},
                :workspace_id,
                id,
                CASE WHEN is_superuser THEN 'super_admin' ELSE COALESCE(role, 'operator') END,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM "user"
            {suffix}
            """
        ),
        {"workspace_id": DEFAULT_WORKSPACE_ID},
    )


def _backfill_campaign_creator_memberships(bind) -> None:  # noqa: ANN001
    if not (_table_exists(bind, "campaigns") and _table_exists(bind, "user")):
        return
    prefix = _insert_ignore_prefix(bind)
    suffix = _on_conflict_suffix(bind, "(workspace_id, user_id)")
    bind.execute(
        sa.text(
            f"""
            {prefix} workspace_memberships (id, workspace_id, user_id, role, status, created_at, updated_at)
            SELECT DISTINCT
                {_uuid_expr(bind)},
                campaigns.workspace_id,
                campaigns.created_by,
                'admin',
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM campaigns
            JOIN "user" ON "user".id = campaigns.created_by
            WHERE campaigns.workspace_id IS NOT NULL AND campaigns.workspace_id <> ''
            {suffix}
            """
        )
    )


def upgrade() -> None:
    """Apply this Alembic migration."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    if not _table_exists(bind, "workspaces"):
        op.create_table(
            "workspaces",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False, server_default="Workspace"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists(bind, "workspace_memberships"):
        op.create_table(
            "workspace_memberships",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(length=50), nullable=False, server_default="operator"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(
                ["workspace_id"],
                ["workspaces.id"],
                name="fk_workspace_memberships_workspace_id",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_workspace_memberships_user_id", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_workspace_user"),
        )
    _create_index_if_missing("workspace_memberships", "idx_workspace_membership_user", ["user_id"])
    _create_index_if_missing("workspace_memberships", "idx_workspace_membership_workspace", ["workspace_id"])
    _create_index_if_missing("workspace_memberships", "ix_workspace_memberships_role", ["role"])
    _create_index_if_missing("workspace_memberships", "ix_workspace_memberships_status", ["status"])

    _insert_default_workspace(bind)
    _backfill_workspaces(bind)
    _backfill_default_user_memberships(bind)
    _backfill_campaign_creator_memberships(bind)


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_index("ix_workspace_memberships_status", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_role", table_name="workspace_memberships")
    op.drop_index("idx_workspace_membership_workspace", table_name="workspace_memberships")
    op.drop_index("idx_workspace_membership_user", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
