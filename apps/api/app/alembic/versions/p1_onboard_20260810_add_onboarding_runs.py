"""persist phase one onboarding runs, stages, and evidence"""

from alembic import op
import sqlalchemy as sa

revision = "p1_onboard_20260810"
down_revision = "p2_control_20260810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("onboarding_run", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("tenant_key", sa.String(128), nullable=False), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("desired_version", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False), sa.Column("actor", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("idempotency_key", name="uq_onboarding_run_idempotency"))
    op.create_index("ix_onboarding_run_tenant_key", "onboarding_run", ["tenant_key"])
    op.create_index("ix_onboarding_run_status", "onboarding_run", ["status"])
    op.create_table("onboarding_stage", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("run_id", sa.Uuid(), nullable=False), sa.Column("stage", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False), sa.Column("result_code", sa.String(64)), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("run_id", "stage", name="uq_onboarding_stage_run_stage"))
    op.create_index("ix_onboarding_stage_run_id", "onboarding_stage", ["run_id"])
    op.create_index("ix_onboarding_stage_status", "onboarding_stage", ["status"])
    op.create_table("onboarding_evidence", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("run_id", sa.Uuid(), nullable=False), sa.Column("stage", sa.String(64), nullable=False), sa.Column("result_code", sa.String(64), nullable=False), sa.Column("digest", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("run_id", "stage", "digest", name="uq_onboarding_evidence_digest"))
    op.create_index("ix_onboarding_evidence_run_id", "onboarding_evidence", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_evidence_run_id", table_name="onboarding_evidence")
    op.drop_table("onboarding_evidence")
    op.drop_index("ix_onboarding_stage_status", table_name="onboarding_stage")
    op.drop_index("ix_onboarding_stage_run_id", table_name="onboarding_stage")
    op.drop_table("onboarding_stage")
    op.drop_index("ix_onboarding_run_status", table_name="onboarding_run")
    op.drop_index("ix_onboarding_run_tenant_key", table_name="onboarding_run")
    op.drop_table("onboarding_run")
