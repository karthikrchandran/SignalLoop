"""add eCRM installation binding and durable projection

Revision ID: p1_ecrm_install_20260812
Revises: p1_revenue_outcomes_20260811
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_ecrm_install_20260812"
down_revision = "p1_revenue_outcomes_20260811"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ecrm_installation_binding",
        sa.Column("workspace_id", sa.String(64), primary_key=True),
        sa.Column("ecrm_cell_id", sa.String(128), nullable=False),
        sa.Column("ecrm_cell_key", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("credential_secret_ref", sa.String(1024), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ecrm_cell_id"),
        sa.UniqueConstraint("ecrm_cell_key"),
    )
    op.create_index("ix_ecrm_installation_binding_ecrm_cell_id", "ecrm_installation_binding", ["ecrm_cell_id"])
    op.create_index("ix_ecrm_installation_binding_ecrm_cell_key", "ecrm_installation_binding", ["ecrm_cell_key"])
    op.create_index("ix_ecrm_installation_binding_status", "ecrm_installation_binding", ["status"])
    op.create_table(
        "ecrm_destination_receipt",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("ecrm_cell_id", sa.String(128), nullable=False),
        sa.Column("source_event_id", sa.String(255), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("stream_key", sa.String(255), nullable=False),
        sa.Column("event_kind", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("fence_token", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("dead_letter_at", sa.DateTime(timezone=True)),
        sa.Column("replayed_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "source_event_id", "event_kind", name="uq_ecrm_receipt_workspace_event_kind"),
        sa.UniqueConstraint("workspace_id", "idempotency_key", name="uq_ecrm_receipt_workspace_idempotency"),
    )
    op.create_index("ix_ecrm_receipt_due", "ecrm_destination_receipt", ["status", "next_attempt_at"])
    op.create_index("ix_ecrm_destination_receipt_workspace_id", "ecrm_destination_receipt", ["workspace_id"])
    op.create_table(
        "ecrm_installation_projection_checkpoint",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("ecrm_cell_id", sa.String(128), nullable=False), sa.Column("stream_key", sa.String(255), nullable=False),
        sa.Column("source_event_id", sa.String(255)), sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("applied_count", sa.Integer(), nullable=False), sa.Column("state", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "stream_key", name="uq_ecrm_checkpoint_workspace_stream"),
    )
    op.create_index("ix_ecrm_installation_projection_checkpoint_workspace_id", "ecrm_installation_projection_checkpoint", ["workspace_id"])
    op.create_table(
        "revenueos_installation_projection",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("ecrm_cell_id", sa.String(128), nullable=False), sa.Column("stream_key", sa.String(255), nullable=False),
        sa.Column("source_event_id", sa.String(255), nullable=False), sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("projection", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "stream_key", name="uq_revenueos_installation_workspace_stream"),
    )
    op.create_index("ix_revenueos_installation_projection_workspace_id", "revenueos_installation_projection", ["workspace_id"])
    op.create_table(
        "ecrm_installation_repair_candidate",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("stream_key", sa.String(255), nullable=False), sa.Column("mismatch_hash", sa.String(64), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False), sa.Column("local_count", sa.Integer(), nullable=False),
        sa.Column("source_checkpoint", sa.Integer(), nullable=False), sa.Column("local_checkpoint", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("resolution", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workspace_id", "stream_key", "mismatch_hash", name="uq_ecrm_repair_mismatch"),
    )
    op.create_index("ix_ecrm_installation_repair_candidate_workspace_id", "ecrm_installation_repair_candidate", ["workspace_id"])


def downgrade() -> None:
    for table in (
        "ecrm_installation_repair_candidate", "revenueos_installation_projection",
        "ecrm_installation_projection_checkpoint", "ecrm_destination_receipt",
        "ecrm_installation_binding",
    ):
        op.drop_table(table)
