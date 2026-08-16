"""Immutable policy, evidence, score, and preparation package persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LeadScoringPolicyStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"


class LeadScoreBand(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    NURTURE = "NURTURE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class LeadScoringPolicy(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "lead_scoring_policy"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "workspace_id", "version", name="uq_lead_scoring_policy_version"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    name: str = Field(default="Default lead scoring", max_length=255)
    version: int = Field(ge=1)
    status: LeadScoringPolicyStatus = Field(
        default=LeadScoringPolicyStatus.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    feature_weights: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    band_thresholds: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    freshness_windows: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    exclusion_rules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    policy_digest: str = Field(max_length=64)
    approved_by: uuid.UUID | None = Field(default=None)
    approved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LeadEvidenceItem(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "lead_evidence_item"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "contact_id",
            "source_type",
            "source_reference",
            "content_digest",
            name="uq_lead_evidence_source_digest",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    contact_id: uuid.UUID = Field(nullable=False, index=True)
    source_type: str = Field(max_length=64)
    source_reference: str = Field(max_length=2048)
    retrieved_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    content_digest: str = Field(max_length=64)
    sensitivity: str = Field(default="INTERNAL", max_length=32)
    freshness: str = Field(default="CURRENT", max_length=32)
    confidence: str = Field(default="MEDIUM", max_length=32)
    redacted_excerpt: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LeadScoreVersion(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "lead_score_version"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "contact_id",
            "version",
            name="uq_lead_score_contact_version",
        ),
        Index("ix_lead_score_workspace_band", "workspace_id", "band"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    agent_deployment_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("agent_deployment.id", ondelete="RESTRICT"), nullable=False, index=True)
    )
    contact_id: uuid.UUID = Field(nullable=False, index=True)
    policy_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("lead_scoring_policy.id", ondelete="RESTRICT"), nullable=False)
    )
    policy_version: int = Field(ge=1)
    version: int = Field(ge=1)
    score: int = Field(ge=0, le=100)
    band: LeadScoreBand = Field(sa_column=Column(String(32), nullable=False, index=True))
    feature_vector: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    contributions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    negative_factors: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    exclusions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    channel_eligibility: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_digest: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LeadPreparationPackage(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "lead_preparation_package"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "contact_id",
            "version",
            name="uq_lead_preparation_contact_version",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    agent_deployment_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("agent_deployment.id", ondelete="RESTRICT"), nullable=False, index=True)
    )
    contact_id: uuid.UUID = Field(nullable=False, index=True)
    score_version_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("lead_score_version.id", ondelete="RESTRICT"), nullable=False)
    )
    version: int = Field(ge=1)
    brief: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    next_action: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    draft_references: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    review_state: str = Field(default="PENDING", max_length=32, index=True)
    content_digest: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
