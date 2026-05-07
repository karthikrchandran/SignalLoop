"""Add role column to user table

Revision ID: a1b2c3d4e5f6
Revises: 1a31ce608336
Create Date: 2026-03-30 00:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "1a31ce608336"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply this Alembic migration."""
    op.add_column(
        "user",
        sa.Column(
            "role",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
            server_default="operator",
        ),
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_column("user", "role")
