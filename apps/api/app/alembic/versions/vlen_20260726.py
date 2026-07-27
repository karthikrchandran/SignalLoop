"""expand the Alembic revision identifier column

Revision ID: vlen_20260726
Revises: x1y2z3a4b5c6
Create Date: 2026-07-26 00:00:00.000000

The platform shared-record revisions use descriptive identifiers longer than
Alembic's legacy 32-character default.  Expanding the metadata column before
those revisions are applied keeps both upgrades and version tracking valid.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "vlen_20260726"
down_revision: str | None = "x1y2z3a4b5c6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Allow descriptive Alembic revision identifiers."""
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Restore the historical identifier length."""
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=128),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
