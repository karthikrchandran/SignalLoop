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


class ProspectingReadyContactPublic(SQLModel):
    """Workspace contact ranked for prospecting follow-up."""

    id: uuid.UUID
    workspace_id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    phone: str | None = None
    timezone: str
    source_channel: str | None = None
    tags: list[str]
    intents: list[str]
    lead_score: int
    priority: str
    priority_reasons: list[str]
    handoff_source: str | None = None
    created_at: datetime


class ProspectingReadyContactsPublic(SQLModel):
    """API response model for ranked prospecting contacts."""

    data: list[ProspectingReadyContactPublic]
    count: int
