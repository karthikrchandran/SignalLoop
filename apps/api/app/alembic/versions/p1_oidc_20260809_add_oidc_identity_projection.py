"""add immutable OIDC identity projection and session version"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_oidc_20260809"
down_revision: str | None = "tenant_20260809"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("auth_session_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("user", "auth_session_version", server_default=None)
    op.create_table(
        "oidc_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_snapshot", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject", name="uq_oidc_identity_issuer_subject"),
    )
    op.create_index("ix_oidc_identity_issuer", "oidc_identity", ["issuer"])
    op.create_index("ix_oidc_identity_user_id", "oidc_identity", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oidc_identity_user_id", table_name="oidc_identity")
    op.drop_index("ix_oidc_identity_issuer", table_name="oidc_identity")
    op.drop_table("oidc_identity")
    op.drop_column("user", "auth_session_version")
