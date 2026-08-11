"""Durable, tenant-scoped RevenueOS intervention records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.domain.tenants.models import utc_now


class RevenueSignalRecord(SQLModel, table=True):
    """Evidence-backed signal whose consent and policy facts gate intervention."""

    __tablename__ = "revenue_signal_record"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_revenue_signal_tenant_key"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    signal_type: str = Field(sa_column=Column(String(128), nullable=False))
    subject_ref: str = Field(sa_column=Column(String(255), nullable=False))
    confidence: float = Field(nullable=False)
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    evidence_hash: str = Field(sa_column=Column(String(255), nullable=False))
    source: str = Field(sa_column=Column(String(128), nullable=False))
    consent_verified: bool = Field(sa_column=Column(Boolean, nullable=False))
    policy_allowed: bool = Field(sa_column=Column(Boolean, nullable=False))
    idempotency_key: str = Field(sa_column=Column(String(255), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RevenueInterventionRecord(SQLModel, table=True):
    """A governed proposal or a durable denial tied to one tenant signal."""

    __tablename__ = "revenue_intervention_record"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_revenue_intervention_tenant_key"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    signal_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("revenue_signal_record.id", ondelete="RESTRICT"), nullable=False, index=True)
    )
    action: str = Field(sa_column=Column(String(128), nullable=False))
    action_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    idempotency_key: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(default="PROPOSED", max_length=32, index=True)
    denial_reason: str | None = Field(default=None, max_length=255)
    approved_by: str | None = Field(default=None, max_length=255)
    approved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RevenueInterventionDispatch(SQLModel, table=True):
    """A persisted dispatch operation that survives worker restarts."""

    __tablename__ = "revenue_intervention_dispatch"
    __table_args__ = (UniqueConstraint("intervention_id", name="uq_revenue_dispatch_intervention"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    intervention_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("revenue_intervention_record.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    status: str = Field(default="PENDING", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    next_attempt_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    lease_expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    provider: str | None = Field(default=None, max_length=128)
    provider_receipt: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    dead_letter_reason: str | None = Field(default=None, max_length=1000)
    last_error: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
