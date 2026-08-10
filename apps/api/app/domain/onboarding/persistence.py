from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from .models import utc_now


class OnboardingRunRecord(SQLModel, table=True):
    __tablename__ = "onboarding_run"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_onboarding_run_idempotency"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_key: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    idempotency_key: str = Field(sa_column=Column(String(255), nullable=False))
    desired_version: str = Field(default="phase1", max_length=64)
    status: str = Field(default="PENDING", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    actor: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OnboardingStageRecord(SQLModel, table=True):
    __tablename__ = "onboarding_stage"
    __table_args__ = (UniqueConstraint("run_id", "stage", name="uq_onboarding_stage_run_stage"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(index=True, nullable=False)
    stage: str = Field(max_length=64, nullable=False)
    status: str = Field(default="PENDING", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    result_code: str | None = Field(default=None, max_length=64)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OnboardingEvidenceRecord(SQLModel, table=True):
    __tablename__ = "onboarding_evidence"
    __table_args__ = (UniqueConstraint("run_id", "stage", "digest", name="uq_onboarding_evidence_digest"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(index=True, nullable=False)
    stage: str = Field(max_length=64, nullable=False)
    result_code: str = Field(max_length=64, nullable=False)
    digest: str = Field(max_length=64, nullable=False)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
