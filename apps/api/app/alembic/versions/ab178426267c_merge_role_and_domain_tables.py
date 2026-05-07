"""merge_role_and_domain_tables

Revision ID: ab178426267c
Revises: a1b2c3d4e5f6, f1a2b3c4d5e6
Create Date: 2026-04-02 21:43:12.501058

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'ab178426267c'
down_revision = ('a1b2c3d4e5f6', 'f1a2b3c4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    """Apply this Alembic migration."""
    pass


def downgrade():
    """Revert this Alembic migration."""
    pass
