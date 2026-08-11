"""Add supervised sales-agent ledger.

This historical revision is retained because local SignalLoop databases had
already applied it before Phase 1 was merged to main.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "sales_agent_20260809"
down_revision: str | None = "psid_20260726"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("initiated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_agent_runs_workspace_id", ["workspace_id"]),
        ("ix_agent_runs_campaign_id", ["campaign_id"]),
        ("ix_agent_runs_initiated_by", ["initiated_by"]),
        ("idx_agent_runs_workspace_created", ["workspace_id", "created_at"]),
    ):
        op.create_index(name, "agent_runs", columns)

    op.create_table(
        "agent_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("shared_contact_id", sa.Uuid(), nullable=False),
        sa.Column("signal_key", sa.String(length=255), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "signal_key", name="uq_agent_signal_run_key"),
    )
    for name, columns in (
        ("ix_agent_signals_workspace_id", ["workspace_id"]),
        ("ix_agent_signals_run_id", ["run_id"]),
        ("ix_agent_signals_shared_contact_id", ["shared_contact_id"]),
        ("idx_agent_signals_workspace_contact", ["workspace_id", "shared_contact_id"]),
        ("idx_agent_signals_workspace_created", ["workspace_id", "created_at"]),
    ):
        op.create_index(name, "agent_signals", columns)

    op.create_table(
        "agent_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("shared_contact_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("draft_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_agent_proposals_workspace_id", ["workspace_id"]),
        ("ix_agent_proposals_run_id", ["run_id"]),
        ("ix_agent_proposals_campaign_id", ["campaign_id"]),
        ("ix_agent_proposals_shared_contact_id", ["shared_contact_id"]),
        ("ix_agent_proposals_action_type", ["action_type"]),
        ("ix_agent_proposals_status", ["status"]),
        ("ix_agent_proposals_expires_at", ["expires_at"]),
        ("idx_agent_proposals_workspace_contact", ["workspace_id", "shared_contact_id"]),
        ("idx_agent_proposals_workspace_created", ["workspace_id", "created_at"]),
    ):
        op.create_index(name, "agent_proposals", columns)

    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["agent_proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_agent_decisions_workspace_id", ["workspace_id"]),
        ("ix_agent_decisions_proposal_id", ["proposal_id"]),
        ("ix_agent_decisions_decided_by", ["decided_by"]),
        ("idx_agent_decisions_workspace_created", ["workspace_id", "created_at"]),
    ):
        op.create_index(name, "agent_decisions", columns)

    op.create_table(
        "agent_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("initiated_by", sa.Uuid(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["agent_proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_agent_attempt_proposal"),
    )
    for name, columns in (
        ("ix_agent_attempts_workspace_id", ["workspace_id"]),
        ("ix_agent_attempts_proposal_id", ["proposal_id"]),
        ("ix_agent_attempts_initiated_by", ["initiated_by"]),
        ("idx_agent_attempts_workspace_created", ["workspace_id", "created_at"]),
    ):
        op.create_index(name, "agent_attempts", columns)

    op.create_table(
        "agent_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_type", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["agent_proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_agent_outcome_proposal"),
    )
    for name, columns in (
        ("ix_agent_outcomes_workspace_id", ["workspace_id"]),
        ("ix_agent_outcomes_proposal_id", ["proposal_id"]),
        ("ix_agent_outcomes_recorded_by", ["recorded_by"]),
        ("idx_agent_outcomes_workspace_created", ["workspace_id", "created_at"]),
    ):
        op.create_index(name, "agent_outcomes", columns)


def downgrade() -> None:
    tables = (
        ("agent_outcomes", ("idx_agent_outcomes_workspace_created", "ix_agent_outcomes_recorded_by", "ix_agent_outcomes_proposal_id", "ix_agent_outcomes_workspace_id")),
        ("agent_attempts", ("idx_agent_attempts_workspace_created", "ix_agent_attempts_initiated_by", "ix_agent_attempts_proposal_id", "ix_agent_attempts_workspace_id")),
        ("agent_decisions", ("idx_agent_decisions_workspace_created", "ix_agent_decisions_decided_by", "ix_agent_decisions_proposal_id", "ix_agent_decisions_workspace_id")),
        ("agent_proposals", ("idx_agent_proposals_workspace_created", "idx_agent_proposals_workspace_contact", "ix_agent_proposals_expires_at", "ix_agent_proposals_status", "ix_agent_proposals_action_type", "ix_agent_proposals_shared_contact_id", "ix_agent_proposals_campaign_id", "ix_agent_proposals_run_id", "ix_agent_proposals_workspace_id")),
        ("agent_signals", ("idx_agent_signals_workspace_created", "idx_agent_signals_workspace_contact", "ix_agent_signals_shared_contact_id", "ix_agent_signals_run_id", "ix_agent_signals_workspace_id")),
        ("agent_runs", ("idx_agent_runs_workspace_created", "ix_agent_runs_initiated_by", "ix_agent_runs_campaign_id", "ix_agent_runs_workspace_id")),
    )
    for table, indexes in tables:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
