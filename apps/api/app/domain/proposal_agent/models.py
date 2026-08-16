"""Durable minimum-content proposal orchestration records."""

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
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProposalJobStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    COMPLETED = "COMPLETED"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    POLICY_DENIED = "POLICY_DENIED"
    DEAD_LETTER = "DEAD_LETTER"
    UNKNOWN_EXTERNAL_OUTCOME = "UNKNOWN_EXTERNAL_OUTCOME"


class ProposalGenerationJob(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "proposal_generation_job"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "workspace_id", "command_key", name="uq_proposal_job_command"
        ),
        Index("ix_proposal_job_poll", "status", "available_at", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    workspace_id: str = Field(max_length=64, index=True)
    deployment_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("agent_deployment.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    ecrm_cell_id: str = Field(max_length=128, index=True)
    client_account_id: str = Field(max_length=255, index=True)
    proposal_id: str = Field(max_length=255, index=True)
    mode: str = Field(max_length=32)
    command_key: str = Field(max_length=255)
    input_digest: str = Field(max_length=64)
    source_digest: str = Field(max_length=64)
    encrypted_request: str = Field(sa_column=Column(Text, nullable=False))
    command_envelope: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    command_digest: str | None = Field(default=None, max_length=64)
    status: ProposalJobStatus = Field(
        default=ProposalJobStatus.PENDING,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=5, ge=1, le=20)
    available_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    lease_token: uuid.UUID | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), index=True)
    )
    command_attempted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    usage_reservation_id: uuid.UUID | None = Field(default=None, index=True)
    last_error_code: str | None = Field(default=None, max_length=64)
    last_error_detail: str | None = Field(default=None, max_length=1000)
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ProposalGenerationEvidence(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "proposal_generation_evidence"
    __table_args__ = (
        UniqueConstraint("job_id", "source_reference", "source_digest", name="uq_proposal_evidence_source"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(max_length=64, index=True)
    job_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("proposal_generation_job.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    source_type: str = Field(max_length=64)
    source_reference: str = Field(max_length=255)
    source_digest: str = Field(max_length=64)
    permitted_use: str = Field(default="PROPOSAL_GENERATION", max_length=64)
    sensitivity: str = Field(default="CLIENT_CONFIDENTIAL", max_length=32)
    retrieved_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ProposalGenerationReceipt(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "proposal_generation_receipt"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_proposal_receipt_job"),
        UniqueConstraint("workspace_id", "ecrm_receipt_id", name="uq_proposal_receipt_external"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(max_length=64, index=True)
    job_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("proposal_generation_job.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    command_key: str = Field(max_length=255, index=True)
    ecrm_receipt_id: str = Field(max_length=255)
    proposal_id: str = Field(max_length=255)
    version_id: str = Field(max_length=255, index=True)
    version_number: int = Field(ge=1)
    content_digest: str = Field(max_length=64)
    artifact_digest: str | None = Field(default=None, max_length=64)
    finalized_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
