"""make eCRM installation stream versions unique

Revision ID: p1_ecrm_install_q_20260812
Revises: p1_ecrm_install_20260812
"""

from __future__ import annotations

from alembic import op

revision = "p1_ecrm_install_q_20260812"
down_revision = "p1_ecrm_install_20260812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_ecrm_receipt_workspace_stream_version",
        "ecrm_destination_receipt",
        ["workspace_id", "stream_key", "source_version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ecrm_receipt_workspace_stream_version",
        "ecrm_destination_receipt",
        type_="unique",
    )
