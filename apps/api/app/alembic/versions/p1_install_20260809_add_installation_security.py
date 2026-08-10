"""add installation workload keys and native projection replay state"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_install_20260809"
down_revision: str | None = "p2_control_20260810"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("suite_product_installation", sa.Column("workload_key_id", sa.String(length=255), nullable=True))
    op.add_column("suite_product_installation", sa.Column("workload_public_key", sa.String(length=255), nullable=True))
    op.add_column("suite_product_installation", sa.Column("workload_key_status", sa.String(length=32), nullable=False, server_default="UNCONFIGURED"))
    op.add_column("suite_product_installation", sa.Column("workload_key_valid_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("suite_product_installation", sa.Column("workload_key_valid_to", sa.DateTime(timezone=True), nullable=True))
    op.add_column("suite_product_installation", sa.Column("workload_key_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_suite_product_installation_workload_key_id", "suite_product_installation", ["workload_key_id"])
    op.create_index("ix_suite_product_installation_workload_key_status", "suite_product_installation", ["workload_key_status"])

    op.create_table(
        "native_projection_cursor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("cursor", sa.String(length=255), nullable=True),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id", name="uq_native_projection_cursor_installation"),
    )
    op.create_index("ix_native_projection_cursor_installation_id", "native_projection_cursor", ["installation_id"])

    op.create_table(
        "native_projection_receipt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id", "event_id", name="uq_native_projection_receipt_event"),
    )
    op.create_index("ix_native_projection_receipt_installation_id", "native_projection_receipt", ["installation_id"])
    op.create_index("ix_native_projection_receipt_event_id", "native_projection_receipt", ["event_id"])

    op.create_table(
        "native_workload_replay",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("jti", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id", "jti", name="uq_native_workload_replay_installation_jti"),
    )
    op.create_index("ix_native_workload_replay_installation_id", "native_workload_replay", ["installation_id"])
    op.create_index("ix_native_workload_replay_jti", "native_workload_replay", ["jti"])


def downgrade() -> None:
    op.drop_index("ix_native_workload_replay_jti", table_name="native_workload_replay")
    op.drop_index("ix_native_workload_replay_installation_id", table_name="native_workload_replay")
    op.drop_table("native_workload_replay")
    op.drop_index("ix_native_projection_receipt_event_id", table_name="native_projection_receipt")
    op.drop_index("ix_native_projection_receipt_installation_id", table_name="native_projection_receipt")
    op.drop_table("native_projection_receipt")
    op.drop_index("ix_native_projection_cursor_installation_id", table_name="native_projection_cursor")
    op.drop_table("native_projection_cursor")
    op.drop_index("ix_suite_product_installation_workload_key_status", table_name="suite_product_installation")
    op.drop_index("ix_suite_product_installation_workload_key_id", table_name="suite_product_installation")
    for name in ("workload_key_version", "workload_key_valid_to", "workload_key_valid_from", "workload_key_status", "workload_public_key", "workload_key_id"):
        op.drop_column("suite_product_installation", name)
