"""Lead Discovery and AI Enrichment data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    String,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LeadMatchConfidence(str, Enum):
    """Confidence category for matching a discovered entity with existing CRM records."""
    EXACT_MATCH = "EXACT_MATCH"
    HIGH_CONFIDENCE_FUZZY = "HIGH_CONFIDENCE_FUZZY"
    AMBIGUOUS_CONFLICT = "AMBIGUOUS_CONFLICT"
    NEW_ENTITY = "NEW_ENTITY"


class LeadFitBand(str, Enum):
    """Overall qualification band computed by the internal AI scoring engine."""
    HOT_OPPORTUNITY = "HOT_OPPORTUNITY"
    HIGH_FIT = "HIGH_FIT"
    NURTURE = "NURTURE"
    UNQUALIFIED = "UNQUALIFIED"


class DiscoveryProviderType(str, Enum):
    """Sources for discovered leads and enrichment data."""
    SANDBOX = "SANDBOX"
    APOLLO = "APOLLO"
    CLAY = "CLAY"
    INTERNAL_AI = "INTERNAL_AI"
    CUSTOM_WEBHOOK = "CUSTOM_WEBHOOK"


class DiscoveredLeadRecord(SQLModel, table=True):
    """Persisted discovered prospect with normalized firmographics and AI scoring."""
    __tablename__ = "discovered_leads"
    __table_args__ = (
        Index("ix_disc_lead_workspace_email", "workspace_id", "email"),
        Index("ix_disc_lead_workspace_domain", "workspace_id", "company_domain"),
        Index("ix_disc_lead_fit_score", "workspace_id", "fit_score"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_column=Column(String, nullable=False, index=True))
    tenant_id: uuid.UUID | None = Field(default=None, nullable=True)

    # Contact Details
    first_name: str = Field(default="", sa_column=Column(String, nullable=False))
    last_name: str = Field(default="", sa_column=Column(String, nullable=False))
    email: str = Field(sa_column=Column(String, nullable=False, index=True))
    phone: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    title: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    seniority: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    department: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Firmographics
    company_name: str = Field(sa_column=Column(String, nullable=False))
    company_domain: str = Field(sa_column=Column(String, nullable=False, index=True))
    industry: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    employee_count: int | None = Field(default=None, nullable=True)
    revenue_range: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    country: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    region: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    city: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Technographics & Signals
    tech_stack_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    intent_signals_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source_provider: DiscoveryProviderType = Field(default=DiscoveryProviderType.SANDBOX)

    # Entity Resolution & Intelligence
    match_confidence: LeadMatchConfidence = Field(default=LeadMatchConfidence.NEW_ENTITY)
    matched_account_id: str | None = Field(default=None, nullable=True)
    fit_score: int = Field(default=0, nullable=False)
    fit_band: LeadFitBand = Field(default=LeadFitBand.UNQUALIFIED)
    score_rationale: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    conversation_starters_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))

    # Promotion Status
    is_promoted: bool = Field(default=False, nullable=False)
    promoted_contact_id: uuid.UUID | None = Field(default=None, nullable=True)
    promoted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class DiscoverySearchQueryLog(SQLModel, table=True):
    """Audit log of lead searches run by users and automated agents."""
    __tablename__ = "discovery_search_query_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_column=Column(String, nullable=False, index=True))
    criteria_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    results_count: int = Field(default=0, nullable=False)
    provider_used: DiscoveryProviderType = Field(default=DiscoveryProviderType.SANDBOX)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
