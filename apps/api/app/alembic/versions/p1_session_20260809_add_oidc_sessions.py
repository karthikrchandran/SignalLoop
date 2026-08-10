"""add server-side OIDC sessions"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "p1_session_20260809"
down_revision: str | None = "p1_oidc_20260809"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "oidc_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_oidc_session_token_digest", "oidc_session", ["token_digest"])
    op.create_index("ix_oidc_session_user_id", "oidc_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oidc_session_user_id", table_name="oidc_session")
    op.drop_index("ix_oidc_session_token_digest", table_name="oidc_session")
    op.drop_table("oidc_session")
