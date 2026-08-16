"""Apply proposal receipt binding and grounding attestation forward.

Revision ID: p1_proposal_hardening_20260816
Revises: p1_lead_governance_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_proposal_hardening_20260816"
down_revision = "p1_lead_governance_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proposal_generation_receipt",
        sa.Column("ecrm_cell_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "proposal_generation_receipt",
        sa.Column("client_account_id", sa.String(255), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE proposal_generation_receipt AS receipt
            SET ecrm_cell_id = job.ecrm_cell_id,
                client_account_id = job.client_account_id
            FROM proposal_generation_job AS job
            WHERE receipt.job_id = job.id
            """
        )
    )
    op.alter_column("proposal_generation_receipt", "ecrm_cell_id", nullable=False)
    op.alter_column(
        "proposal_generation_receipt", "client_account_id", nullable=False
    )
    op.create_index(
        "ix_proposal_generation_receipt_ecrm_cell_id",
        "proposal_generation_receipt",
        ["ecrm_cell_id"],
    )
    op.create_index(
        "ix_proposal_generation_receipt_client_account_id",
        "proposal_generation_receipt",
        ["client_account_id"],
    )

    for name, type_ in (
        ("ecrm_cell_id", sa.String(128)),
        ("client_account_id", sa.String(255)),
        ("source_version", sa.String(128)),
        ("evidence_receipt_id", sa.String(255)),
    ):
        op.add_column(
            "proposal_grounding_source", sa.Column(name, type_, nullable=True)
        )
    op.add_column(
        "proposal_grounding_source", sa.Column("approved_by", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "proposal_grounding_source",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE proposal_grounding_source
            SET ecrm_cell_id = 'LEGACY_UNATTESTED',
                client_account_id = 'LEGACY_UNATTESTED',
                source_version = 'legacy',
                evidence_receipt_id = 'migration:unattested:' || id::text,
                status = 'DRAFT'
            WHERE ecrm_cell_id IS NULL
            """
        )
    )
    for name in (
        "ecrm_cell_id",
        "client_account_id",
        "source_version",
        "evidence_receipt_id",
    ):
        op.alter_column("proposal_grounding_source", name, nullable=False)
    for name in ("ecrm_cell_id", "client_account_id", "approved_by"):
        op.create_index(
            f"ix_proposal_grounding_source_{name}",
            "proposal_grounding_source",
            [name],
        )


def downgrade() -> None:
    for name in ("approved_by", "client_account_id", "ecrm_cell_id"):
        op.drop_index(
            f"ix_proposal_grounding_source_{name}",
            table_name="proposal_grounding_source",
        )
    for name in (
        "approved_at",
        "approved_by",
        "evidence_receipt_id",
        "source_version",
        "client_account_id",
        "ecrm_cell_id",
    ):
        op.drop_column("proposal_grounding_source", name)
    op.drop_index(
        "ix_proposal_generation_receipt_client_account_id",
        table_name="proposal_generation_receipt",
    )
    op.drop_index(
        "ix_proposal_generation_receipt_ecrm_cell_id",
        table_name="proposal_generation_receipt",
    )
    op.drop_column("proposal_generation_receipt", "client_account_id")
    op.drop_column("proposal_generation_receipt", "ecrm_cell_id")
