"""Keyword-based email signal detection for MVP.

No LLM needed — simple keyword matching is sufficient for detecting
positive reply intent from email responses.
"""
from __future__ import annotations

from dataclasses import dataclass, field


POSITIVE_KEYWORDS = [
    "interested",
    "yes",
    "let's talk",
    "schedule",
    "demo",
    "call me",
    "sounds good",
    "tell me more",
    "set up a time",
    "let's set up",
    "love to",
    "would like to",
    "count me in",
]


@dataclass
class SignalResult:
    """Result row: signal."""
    signal_type: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


def detect_email_signal(reply_text: str) -> SignalResult:
    """Analyze reply text for positive intent signals.

    Returns a SignalResult with:
    - signal_type: "email_positive_reply" or "neutral"
    - confidence: 0.0-1.0 based on keyword matches
    - matched_keywords: list of matched keyword phrases
    """
    if not reply_text:
        return SignalResult(signal_type="neutral", confidence=0.0)

    text_lower = reply_text.lower()
    matched = [kw for kw in POSITIVE_KEYWORDS if kw in text_lower]

    if not matched:
        return SignalResult(signal_type="neutral", confidence=0.0)

    confidence = 0.6 if len(matched) == 1 else 0.9
    return SignalResult(
        signal_type="email_positive_reply",
        confidence=min(confidence, 1.0),
        matched_keywords=matched,
    )
