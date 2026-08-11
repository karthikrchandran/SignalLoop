"""Merge the historical sales-agent ledger with Phase 1."""

from __future__ import annotations

revision: str = "p1_merge_20260810"
down_revision: tuple[str, str] = ("sales_agent_20260809", "p1_onboard_20260810")
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
