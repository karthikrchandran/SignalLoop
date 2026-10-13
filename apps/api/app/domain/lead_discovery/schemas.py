"""Pydantic schemas and DTOs for Lead Discovery and AI Enrichment."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.domain.lead_discovery.models import (
    DiscoveryProviderType,
    LeadFitBand,
    LeadMatchConfidence,
)


class DiscoverySearchCriteria(BaseModel):
    """Firmographic and demographic search parameters."""
    industries: list[str] = Field(default_factory=list, description="Target industries (e.g. SaaS, Fintech, Healthcare)")
    revenue_min: float | None = Field(default=None, description="Minimum estimated revenue in USD")
    revenue_max: float | None = Field(default=None, description="Maximum estimated revenue in USD")
    employee_min: int | None = Field(default=None, description="Minimum headcount")
    employee_max: int | None = Field(default=None, description="Maximum headcount")
    countries: list[str] = Field(default_factory=list, description="Target countries (e.g. US, UK, CA)")
    regions: list[str] = Field(default_factory=list, description="Target states/regions (e.g. California, Texas)")
    job_titles: list[str] = Field(default_factory=list, description="Target job titles (e.g. VP Sales, CTO, Head of Growth)")
    seniority_levels: list[str] = Field(default_factory=list, description="C-Level, VP, Director, Manager")
    tech_stack: list[str] = Field(default_factory=list, description="Technologies used (e.g. Salesforce, AWS, Snowflake)")
    keywords: list[str] = Field(default_factory=list, description="Keyword search in company or role description")
    limit: int = Field(default=25, ge=1, le=100)


class DiscoveredLeadDTO(BaseModel):
    """Public representation of a discovered lead."""
    id: uuid.UUID
    workspace_id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    company_name: str
    company_domain: str
    industry: str | None = None
    employee_count: int | None = None
    revenue_range: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    source_provider: DiscoveryProviderType
    match_confidence: LeadMatchConfidence
    matched_account_id: str | None = None
    fit_score: int
    fit_band: LeadFitBand
    score_rationale: str | None = None
    conversation_starters: list[str] = Field(default_factory=list)
    is_promoted: bool = False
    promoted_contact_id: uuid.UUID | None = None
    created_at: datetime


class DiscoverySearchResponse(BaseModel):
    """Response containing discovered leads matching filter criteria."""
    total: int
    leads: list[DiscoveredLeadDTO]
    provider_used: DiscoveryProviderType
    criteria: DiscoverySearchCriteria


class EnrichmentRequest(BaseModel):
    """Enrichment request by domain or company name or contact email."""
    domain: str | None = None
    company_name: str | None = None
    email: str | None = None
    providers: list[DiscoveryProviderType] | None = None


class EnrichmentResponse(BaseModel):
    """Enrichment result combining firmographics, technologies, and verified contacts."""
    company_name: str
    domain: str
    industry: str | None = None
    employee_count: int | None = None
    revenue_range: str | None = None
    country: str | None = None
    region: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    key_contacts: list[dict] = Field(default_factory=list)
    enrichment_source: DiscoveryProviderType


class LeadScoreContribution(BaseModel):
    """Individual points contributing to the total lead fit score."""
    pillar: str
    points: int
    max_points: int
    reason: str


class LeadScoringResponse(BaseModel):
    """AI score breakdown and opportunity rationale."""
    fit_score: int
    fit_band: LeadFitBand
    contributions: list[LeadScoreContribution]
    rationale: str
    conversation_starters: list[str]
    suggested_channels: list[str]


class LeadPromotionRequest(BaseModel):
    """Request to promote a discovered lead into the workspace CRM contacts."""
    lead_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    sequence_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)


class LeadPromotionResponse(BaseModel):
    """Result of promoting a discovered lead."""
    lead_id: uuid.UUID
    contact_id: uuid.UUID
    workspace_id: str
    enrolled_campaign_id: uuid.UUID | None = None
    enrolled_sequence_id: uuid.UUID | None = None
    status: str
    message: str
