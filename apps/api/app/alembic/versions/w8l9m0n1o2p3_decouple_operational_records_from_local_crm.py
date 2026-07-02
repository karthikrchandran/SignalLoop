"""decouple operational records from local crm

Revision ID: w8l9m0n1o2p3
Revises: v7k8l9m0n1o2
Create Date: 2026-06-30 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op

revision: str = "w8l9m0n1o2p3"
down_revision: str | tuple[str, ...] | None = "v7k8l9m0n1o2"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}

LOCAL_CRM_FOREIGN_KEYS: tuple[tuple[str, str, str, str], ...] = (
    ("contacts", "account_id", "accounts", "id"),
    ("prospecting_snapshots", "contact_id", "contacts", "id"),
    ("contact_progression", "contact_id", "contacts", "id"),
    ("contact_state_history", "contact_id", "contacts", "id"),
    ("action_queue", "contact_id", "contacts", "id"),
    ("contact_events", "contact_id", "contacts", "id"),
    ("routing_decisions", "contact_id", "contacts", "id"),
    ("dead_letter_events", "contact_id", "contacts", "id"),
    ("contact_sequence_state", "contact_id", "contacts", "id"),
    ("signal_events", "contact_id", "contacts", "id"),
    ("scheduling_requests", "contact_id", "contacts", "id"),
    ("call_requests", "contact_id", "contacts", "id"),
    ("chatbot_conversations", "contact_id", "contacts", "id"),
    ("chatbot_opt_outs", "contact_id", "contacts", "id"),
)


def _constraint_names(
    *,
    table_name: str,
    column_name: str,
    referred_table: str,
) -> Iterable[str]:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("constrained_columns") != [column_name]:
            continue
        if foreign_key.get("referred_table") != referred_table:
            continue
        name = foreign_key.get("name")
        if isinstance(name, str) and name:
            yield name
        else:
            yield f"fk_{table_name}_{column_name}_{referred_table}"


def upgrade() -> None:
    """Drop master-data foreign keys so operational rows can use shared-record ids."""
    for table_name, column_name, referred_table, _ in LOCAL_CRM_FOREIGN_KEYS:
        constraint_names = list(
            _constraint_names(
                table_name=table_name,
                column_name=column_name,
                referred_table=referred_table,
            )
        )
        if not constraint_names:
            continue
        with op.batch_alter_table(
            table_name,
            naming_convention=NAMING_CONVENTION,
        ) as batch_op:
            for constraint_name in constraint_names:
                batch_op.drop_constraint(constraint_name, type_="foreignkey")


def downgrade() -> None:
    """Restore local CRM master-data foreign keys."""
    for (
        table_name,
        column_name,
        referred_table,
        referred_column,
    ) in LOCAL_CRM_FOREIGN_KEYS:
        with op.batch_alter_table(
            table_name,
            naming_convention=NAMING_CONVENTION,
        ) as batch_op:
            batch_op.create_foreign_key(
                f"fk_{table_name}_{column_name}_{referred_table}",
                referred_table,
                [column_name],
                [referred_column],
            )
