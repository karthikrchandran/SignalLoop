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


class ProspectingBulkResearchRequest(SQLModel):
    """Request payload for running prospecting research for selected contacts."""

    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
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


class ProspectingEnrollmentRequest(SQLModel):
    """Request payload for adding selected prospects to outreach."""

    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    campaign_id: uuid.UUID
    sequence_id: uuid.UUID | None = None


class ProspectingEnrollmentPublic(SQLModel):
    """API response model for selected prospect enrollment."""

    selected_count: int
    campaign_added_count: int
    campaign_existing_count: int
    sequence_enrolled_count: int = 0
    sequence_existing_count: int = 0
    message: str


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
