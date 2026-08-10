"""close workspace isolation for suppression and dispatch jobs

Revision ID: tenant_20260809
Revises: psid_20260726
Create Date: 2026-08-09 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_20260809"
down_revision: str | None = "psid_20260726"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

LEGACY_WORKSPACE_ID = "default"


def _add_workspace_column(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            "workspace_id",
            sa.String(length=64),
            nullable=True,
            server_default=LEGACY_WORKSPACE_ID,
        ),
    )


def _finish_workspace_column(table_name: str, index_name: str) -> None:
    op.alter_column(
        table_name,
        "workspace_id",
        existing_type=sa.String(length=64),
        nullable=False,
        server_default=None,
    )
    op.create_index(index_name, table_name, ["workspace_id"])


def upgrade() -> None:
    """Anchor dispatch, suppression, replay, and retry state to a workspace."""
    _add_workspace_column("email_suppressions")
    _finish_workspace_column(
        "email_suppressions",
        "ix_email_suppressions_workspace_id",
    )
    op.drop_constraint(
        "uq_suppression_email_reason",
        "email_suppressions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_suppression_workspace_email_reason",
        "email_suppressions",
        ["workspace_id", "email", "reason"],
    )

    _add_workspace_column("call_requests")
    op.execute(
        sa.text(
            """
            UPDATE call_requests AS call_request
            SET workspace_id = campaign.workspace_id
            FROM campaigns AS campaign
            WHERE campaign.id = call_request.campaign_id
            """
        )
    )
    _finish_workspace_column("call_requests", "ix_call_requests_workspace_id")

    _add_workspace_column("action_queue")
    op.execute(
        sa.text(
            """
            UPDATE action_queue AS action
            SET workspace_id = campaign.workspace_id
            FROM campaigns AS campaign
            WHERE campaign.id = action.campaign_id
            """
        )
    )
    _finish_workspace_column("action_queue", "ix_action_queue_workspace_id")

    _add_workspace_column("send_requests")
    op.execute(
        sa.text(
            """
            UPDATE send_requests AS send_request
            SET workspace_id = campaign.workspace_id
            FROM contact_sequence_state AS state
            JOIN email_sequences AS sequence ON sequence.id = state.sequence_id
            JOIN campaigns AS campaign ON campaign.id = sequence.campaign_id
            WHERE state.id = send_request.contact_sequence_state_id
            """
        )
    )
    _finish_workspace_column("send_requests", "ix_send_requests_workspace_id")
    op.create_index(
        "ix_send_requests_idempotency_key",
        "send_requests",
        ["idempotency_key"],
    )
    op.drop_constraint(
        "uq_send_request_idempotency_key",
        "send_requests",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_send_request_workspace_idempotency",
        "send_requests",
        ["workspace_id", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_send_request_workspace_provider_message",
        "send_requests",
        ["workspace_id", "provider_message_id"],
    )

    op.drop_constraint(
        "uq_provider_event_provider_event_id",
        "provider_event_logs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_event_workspace_provider_event_id",
        "provider_event_logs",
        ["workspace_id", "provider", "provider_event_id"],
    )


def downgrade() -> None:
    """Restore the pre-isolation schema when no cross-workspace duplicates exist."""
    op.drop_constraint(
        "uq_provider_event_workspace_provider_event_id",
        "provider_event_logs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_event_provider_event_id",
        "provider_event_logs",
        ["provider", "provider_event_id"],
    )

    op.drop_constraint(
        "uq_send_request_workspace_provider_message",
        "send_requests",
        type_="unique",
    )
    op.drop_constraint(
        "uq_send_request_workspace_idempotency",
        "send_requests",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_send_request_idempotency_key",
        "send_requests",
        ["idempotency_key"],
    )
    op.drop_index("ix_send_requests_idempotency_key", table_name="send_requests")
    op.drop_index("ix_send_requests_workspace_id", table_name="send_requests")
    op.drop_column("send_requests", "workspace_id")

    op.drop_index("ix_call_requests_workspace_id", table_name="call_requests")
    op.drop_column("call_requests", "workspace_id")

    op.drop_index("ix_action_queue_workspace_id", table_name="action_queue")
    op.drop_column("action_queue", "workspace_id")

    op.drop_constraint(
        "uq_suppression_workspace_email_reason",
        "email_suppressions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_suppression_email_reason",
        "email_suppressions",
        ["email", "reason"],
    )
    op.drop_index(
        "ix_email_suppressions_workspace_id",
        table_name="email_suppressions",
    )
    op.drop_column("email_suppressions", "workspace_id")
