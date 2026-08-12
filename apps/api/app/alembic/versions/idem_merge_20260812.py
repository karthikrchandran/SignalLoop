"""merge durable idempotency and revenue outcome heads"""

from __future__ import annotations

revision = "idem_merge_20260812"
down_revision = ("idem_lifecycle_20260812", "p1_revenue_outcomes_20260811")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
