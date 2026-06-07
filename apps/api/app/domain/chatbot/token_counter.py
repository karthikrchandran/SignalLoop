"""Session token budgeting helpers for ChatBot Hub."""

from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str | None) -> int:
    """Estimate tokens cheaply enough for worker-side budget checks."""
    normalized = " ".join((text or "").split())
    if not normalized:
        return 0
    by_words = int(len(normalized.split()) * 1.33)
    by_chars = int(len(normalized) / 4)
    return max(1, by_words, by_chars)


@dataclass
class TokenBudgetTracker:
    """Tracks the per-session token cap."""

    cap: int
    used: int = 0

    @property
    def exhausted(self) -> bool:
        return self.cap > 0 and self.used >= self.cap

    def can_spend(self, estimated_tokens: int) -> bool:
        if self.cap <= 0:
            return True
        return self.used + max(0, estimated_tokens) <= self.cap

    def add(self, *texts: str | None) -> int:
        spent = sum(estimate_tokens(text) for text in texts)
        self.used += spent
        return spent

