"""scope onboarding idempotency and persist recovery evidence

Revision ID: onboarding_hardening_20260812
Revises: phase1_merge_20260812, p1_ecrm_install_q_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "onboarding_hardening_20260812"
down_revision = ("phase1_merge_20260812", "p1_ecrm_install_q_20260812")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onboarding_run", sa.Column("input_hash", sa.String(length=64), nullable=True))
    op.execute("UPDATE onboarding_run SET input_hash = repeat('0', 64) WHERE input_hash IS NULL")
    op.alter_column("onboarding_run", "input_hash", nullable=False)
    op.add_column("onboarding_run", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_onboarding_run_idempotency", "onboarding_run", type_="unique")
    op.create_unique_constraint("uq_onboarding_run_scope_idempotency", "onboarding_run", ["tenant_key", "desired_version", "idempotency_key", "input_hash"])
    op.add_column("onboarding_stage", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "onboarding_evidence_bundle",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("canonical_payload", sa.String(), nullable=False),
        sa.Column("public_key", sa.String(length=128), nullable=False),
        sa.Column("signature", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "digest", name="uq_onboarding_evidence_bundle_digest"),
    )
    op.create_index("ix_onboarding_evidence_bundle_run_id", "onboarding_evidence_bundle", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_evidence_bundle_run_id", table_name="onboarding_evidence_bundle")
    op.drop_table("onboarding_evidence_bundle")
    op.drop_column("onboarding_stage", "lease_expires_at")
    op.drop_constraint("uq_onboarding_run_scope_idempotency", "onboarding_run", type_="unique")
    op.create_unique_constraint("uq_onboarding_run_idempotency", "onboarding_run", ["idempotency_key"])
    op.drop_column("onboarding_run", "lease_expires_at")
    op.drop_column("onboarding_run", "input_hash")
