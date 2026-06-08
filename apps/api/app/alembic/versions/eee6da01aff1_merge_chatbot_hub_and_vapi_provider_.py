"""merge chatbot hub and vapi provider heads

Revision ID: eee6da01aff1
Revises: s4h5i6j7k8l9, t5i6j7k8l9m0
Create Date: 2026-06-07 22:56:31.276429

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'eee6da01aff1'
down_revision = ('s4h5i6j7k8l9', 't5i6j7k8l9m0')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
