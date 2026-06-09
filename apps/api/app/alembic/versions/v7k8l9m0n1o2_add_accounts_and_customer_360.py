"""add accounts and customer 360

Revision ID: v7k8l9m0n1o2
Revises: u6j7k8l9m0n1
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

import re
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "v7k8l9m0n1o2"
down_revision: str | tuple[str, ...] | None = "u6j7k8l9m0n1"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _account_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def _uuid_value(bind) -> str:  # noqa: ANN001
    value = uuid.uuid4()
    if bind.dialect.name == "postgresql":
        return str(value)
    return value.hex


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_key", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("workspace_id", "account_key", name="uq_account_workspace_key"),
    )
    op.create_index("ix_accounts_workspace_id", "accounts", ["workspace_id"])
    op.create_index("ix_accounts_account_key", "accounts", ["account_key"])
    op.create_index("idx_accounts_workspace_name", "accounts", ["workspace_id", "name"])

    with op.batch_alter_table("contacts") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_contacts_account_id_accounts",
            "accounts",
            ["account_id"],
            ["id"],
        )
        batch_op.create_index("ix_contacts_account_id", ["account_id"])

    bind = op.get_bind()
    contact_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT workspace_id, company
                FROM contacts
                WHERE company IS NOT NULL AND trim(company) <> ''
                GROUP BY workspace_id, company
                ORDER BY workspace_id, company
                """
            )
        ).mappings()
    )
    account_ids: dict[tuple[str, str], str] = {}
    for row in contact_rows:
        workspace_id = row["workspace_id"]
        company = row["company"].strip()
        key = _account_key(company)
        if not key:
            continue
        map_key = (workspace_id, key)
        if map_key in account_ids:
            continue
        account_id = _uuid_value(bind)
        account_ids[map_key] = account_id
        bind.execute(
            sa.text(
                """
                INSERT INTO accounts (id, workspace_id, name, account_key, status, created_at, updated_at)
                VALUES (:id, :workspace_id, :name, :account_key, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": account_id,
                "workspace_id": workspace_id,
                "name": company,
                "account_key": key,
            },
        )

    contacts = list(
        bind.execute(
            sa.text(
                """
                SELECT id, workspace_id, company
                FROM contacts
                WHERE company IS NOT NULL AND trim(company) <> ''
                """
            )
        ).mappings()
    )
    for contact in contacts:
        key = _account_key(contact["company"])
        account_id = account_ids.get((contact["workspace_id"], key))
        if account_id:
            bind.execute(
                sa.text("UPDATE contacts SET account_id = :account_id WHERE id = :contact_id"),
                {"account_id": account_id, "contact_id": contact["id"]},
            )


def downgrade() -> None:
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.drop_index("ix_contacts_account_id")
        batch_op.drop_constraint("fk_contacts_account_id_accounts", type_="foreignkey")
        batch_op.drop_column("account_id")
    op.drop_index("idx_accounts_workspace_name", table_name="accounts")
    op.drop_index("ix_accounts_account_key", table_name="accounts")
    op.drop_index("ix_accounts_workspace_id", table_name="accounts")
    op.drop_table("accounts")
