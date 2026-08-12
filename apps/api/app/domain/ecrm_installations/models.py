"""Persistence models for the SignalLoop/eCRM installation boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EcrmInstallationBinding(SQLModel, table=True):
    __tablename__ = "ecrm_installation_binding"

    workspace_id: str = Field(primary_key=True, max_length=64)
    ecrm_cell_id: str = Field(sa_column=Column(String(128), nullable=False, unique=True, index=True))
    ecrm_cell_key: str = Field(sa_column=Column(String(128), nullable=False, unique=True, index=True))
    base_url: str = Field(max_length=2048)
    credential_secret_ref: str = Field(max_length=1024)
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    verified_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    rotated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    source_version: int = Field(default=1, nullable=False)
    consecutive_failures: int = Field(default=0, nullable=False)
    circuit_open_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DestinationReceipt(SQLModel, table=True):
    __tablename__ = "ecrm_destination_receipt"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_event_id", "event_kind", name="uq_ecrm_receipt_workspace_event_kind"),
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_ecrm_receipt_workspace_idempotency"),
        UniqueConstraint(
            "workspace_id",
            "stream_key",
            "source_version",
            name="uq_ecrm_receipt_workspace_stream_version",
        ),
        Index("ix_ecrm_receipt_due", "status", "next_attempt_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    ecrm_cell_id: str = Field(max_length=128, index=True)
    source_event_id: str = Field(max_length=255, index=True)
    source_version: int = Field(nullable=False)
    stream_key: str = Field(max_length=255, index=True)
    event_kind: str = Field(max_length=64)
    idempotency_key: str = Field(max_length=255)
    payload_hash: str = Field(max_length=64)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default="RECEIVED", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    next_attempt_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    lease_owner: str | None = Field(default=None, max_length=128)
    lease_expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    fence_token: int = Field(default=0, nullable=False)
    last_error: str | None = Field(default=None, max_length=1000)
    dead_letter_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    replayed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    received_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class InstallationProjectionCheckpoint(SQLModel, table=True):
    __tablename__ = "ecrm_installation_projection_checkpoint"
    __table_args__ = (
        UniqueConstraint("workspace_id", "stream_key", name="uq_ecrm_checkpoint_workspace_stream"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    ecrm_cell_id: str = Field(max_length=128)
    stream_key: str = Field(max_length=255)
    source_event_id: str | None = Field(default=None, max_length=255)
    source_version: int = Field(default=0, nullable=False)
    applied_count: int = Field(default=0, nullable=False)
    state: str = Field(default="CURRENT", max_length=32)
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RevenueOsInstallationProjection(SQLModel, table=True):
    __tablename__ = "revenueos_installation_projection"
    __table_args__ = (UniqueConstraint("workspace_id", "stream_key", name="uq_revenueos_installation_workspace_stream"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    ecrm_cell_id: str = Field(max_length=128)
    stream_key: str = Field(max_length=255)
    source_event_id: str = Field(max_length=255)
    source_version: int = Field(nullable=False)
    payload_hash: str = Field(max_length=64)
    projection: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class InstallationRepairCandidate(SQLModel, table=True):
    __tablename__ = "ecrm_installation_repair_candidate"
    __table_args__ = (
        UniqueConstraint("workspace_id", "stream_key", "mismatch_hash", name="uq_ecrm_repair_mismatch"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    stream_key: str = Field(max_length=255)
    mismatch_hash: str = Field(max_length=64)
    source_count: int = Field(nullable=False)
    local_count: int = Field(nullable=False)
    source_checkpoint: int = Field(nullable=False)
    local_checkpoint: int = Field(nullable=False)
    status: str = Field(default="OPEN", max_length=32, index=True)
    resolution: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
