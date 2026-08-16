"""Strict API contracts for Lead Preparation Agent administration."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.lead_preparation.models import (
    LeadPreparationJobStatus,
    LeadScoreBand,
    LeadScoringPolicyStatus,
)


class LeadPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    version: int = Field(ge=1)
    feature_weights: dict[str, int]
    band_thresholds: dict[str, int]
    freshness_windows: dict[str, int]
    exclusion_rules: list[str]

    @model_validator(mode="after")
    def validate_policy(self) -> LeadPolicyCreate:
        if not self.feature_weights or any(
            value < 0 or value > 100 for value in self.feature_weights.values()
        ):
            raise ValueError("feature weights must be between zero and one hundred")
        hot = self.band_thresholds.get("HOT")
        warm = self.band_thresholds.get("WARM")
        if hot is None or warm is None or not 0 <= warm < hot <= 100:
            raise ValueError("HOT and WARM thresholds must be ordered within 0..100")
        recent = self.freshness_windows.get("recent_activity_days")
        if recent is None or recent < 1 or recent > 3650:
            raise ValueError("recent activity window must be within 1..3650 days")
        return self


class LeadPolicyDryRun(LeadPolicyCreate):
    contact_id: uuid.UUID


class LeadPolicyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    workspace_id: str
    name: str
    version: int
    status: LeadScoringPolicyStatus
    feature_weights: dict[str, int]
    band_thresholds: dict[str, int]
    freshness_windows: dict[str, int]
    exclusion_rules: list[str]
    policy_digest: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime


class LeadScoreDryRunPublic(BaseModel):
    score: int
    band: LeadScoreBand
    contributions: list[dict[str, Any]]
    reasons: list[str]
    negative_factors: list[str]
    exclusions: list[str]
    channel_eligibility: dict[str, bool]


class LeadPreparationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    deployment_id: uuid.UUID
    contact_id: uuid.UUID
    policy_id: uuid.UUID
    event_key: str = Field(min_length=1, max_length=255)
    max_attempts: int = Field(default=5, ge=1, le=20)


class LeadPreparationJobPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    workspace_id: str
    deployment_id: uuid.UUID
    contact_id: uuid.UUID
    policy_id: uuid.UUID
    event_key: str
    status: LeadPreparationJobStatus
    attempt_count: int
    max_attempts: int
    available_at: datetime
    score_version_id: uuid.UUID | None
    package_id: uuid.UUID | None
    last_error_code: str | None
    completed_at: datetime | None
    created_at: datetime


class LeadPackagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    workspace_id: str
    agent_deployment_id: uuid.UUID
    contact_id: uuid.UUID
    score_version_id: uuid.UUID
    version: int
    brief: dict[str, Any]
    next_action: dict[str, Any]
    draft_references: dict[str, Any]
    review_state: str
    content_digest: str
    created_at: datetime


class LeadPackageDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class LeadPackageRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = Field(pattern=r"^(email|voice)$")


class LeadOutcomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=64)
    contact_id: uuid.UUID
    policy_id: uuid.UUID
    outcome_type: str = Field(min_length=2, max_length=64)
    outcome_reference: str = Field(min_length=1, max_length=255)
    observed_at: datetime


class LeadOutcomePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    workspace_id: str
    contact_id: uuid.UUID
    policy_id: uuid.UUID
    policy_version: int
    outcome_type: str
    outcome_reference: str
    observed_at: datetime
    created_at: datetime
