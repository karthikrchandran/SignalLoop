from __future__ import annotations

from app.domain.outreach.token_service import parse_tokens


def token_density(content: str) -> float:
    words = max(len(content.split()), 1)
    return len(parse_tokens(content)) / words
