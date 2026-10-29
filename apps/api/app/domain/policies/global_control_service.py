"""Domain service: ``global control service``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def apply_pause_state(reason: str) -> dict[str, Any]:
    """Apply pause state."""
    return {
        "paused": True,
        "paused_reason": reason,
        "paused_at": datetime.now(UTC),
    }
