"""merge Phase 1 projection recovery and durable idempotency heads"""

from __future__ import annotations

revision = "phase1_merge_20260812"
down_revision = ("p1_projection_recovery_20260812", "idem_merge_20260812")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
