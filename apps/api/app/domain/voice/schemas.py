"""Request/response schemas for the ``voice`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel


class ScriptCreate(SQLModel):
    """Request payload for creating script."""
    name: str
    campaign_id: uuid.UUID
    content: str


class ScriptUpdate(SQLModel):
    """Request payload for updating script."""
    name: str | None = None
    content: str | None = None
    active: bool | None = None


class QAPairPublic(SQLModel):
    """API response model: q a pair."""
    question: str
    answer: str


class ScriptParsedPublic(SQLModel):
    """API response model: script parsed."""
    opening_pitch: str
    qa_pairs: list[QAPairPublic]
    fallback_response: str
    scheduling_question: str


class ScriptPublic(SQLModel):
    """API response model: script."""
    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class ScriptDetailPublic(ScriptPublic):
    """API response model: script detail."""
    content: str
    parsed: ScriptParsedPublic | None = None


class ScriptsPublic(SQLModel):
    """API response model: scripts."""
    data: list[ScriptPublic]
    count: int
