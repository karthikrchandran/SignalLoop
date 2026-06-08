from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ProspectingSource(SQLModel):
    """Source summary used to create a prospecting brief."""

    label: str = Field(max_length=128)
    summary: str = Field(max_length=2000)


class ProspectingBrief(SQLModel):
    """Structured prospecting research output."""

    account_summary: str
    pain_points: list[str]
    objections: list[str]
    personalization_bullets: list[str]
    suggested_next_action: str
    email_draft: str
    voice_opener: str


class ProspectingResearchRequest(SQLModel):
    """Request payload for running prospecting research."""

    contact_id: uuid.UUID
    company_url: str | None = Field(default=None, max_length=2048)


class ProspectingResearchPublic(ProspectingBrief):
    """API response model for a prospecting snapshot."""

    id: uuid.UUID
    contact_id: uuid.UUID
    company_url: str | None = None
    sources: list[ProspectingSource]
    created_at: datetime


class ProspectingResearchListPublic(SQLModel):
    """API response model for prospecting snapshots."""

    data: list[ProspectingResearchPublic]
    count: int
