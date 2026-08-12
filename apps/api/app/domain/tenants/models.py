"""Tenant control-plane persistence models."""

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


class ProductCode(str, Enum):
    COMMIT_ARC = "commitarc"
    REVENUE_OS = "revenueos"
    SIGNAL_LOOP = "signalloop"


class RoleBundle(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ENGAGEMENT_OPERATOR = "ENGAGEMENT_OPERATOR"
    TENANT_OWNER = "TENANT_OWNER"
    REVENUE_OS_ADMIN = "REVENUE_OS_ADMIN"
    COMMIT_ARC_ADMIN = "COMMIT_ARC_ADMIN"
    ENGAGEMENT_ADMIN = "ENGAGEMENT_ADMIN"


class PlatformRole(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    PLATFORM_SUPPORT = "PLATFORM_SUPPORT"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(SQLModel, table=True):
    __tablename__ = "suite_tenant"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(sa_column=Column(String(128), nullable=False, unique=True, index=True))
    display_name: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(default="ACTIVE", max_length=32)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TenantEntitlement(SQLModel, table=True):
    __tablename__ = "suite_tenant_entitlement"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "product_code", name="uq_suite_entitlement_tenant_product"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    product_code: ProductCode = Field(sa_column=Column(String(32), nullable=False))
    status: str = Field(default="ACTIVE", max_length=32)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TenantInvitation(SQLModel, table=True):
    __tablename__ = "suite_tenant_invitation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    email: str = Field(sa_column=Column(String(320), nullable=False))
    token_digest: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    status: str = Field(default="PENDING", max_length=32)
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    accepted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class SuiteMembership(SQLModel, table=True):
    """A user's suite-level membership in one tenant."""

    __tablename__ = "suite_membership"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_suite_membership_tenant_user"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SuiteRoleAssignment(SQLModel, table=True):
    """A composable role bundle assigned to a suite membership."""

    __tablename__ = "suite_role_assignment"
    __table_args__ = (
        UniqueConstraint("membership_id", "role_bundle", name="uq_suite_role_assignment_membership_bundle"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    membership_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_membership.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    role_bundle: RoleBundle = Field(sa_column=Column(String(64), nullable=False))
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ProductInstallation(SQLModel, table=True):
    """Tenant entitlement mapped to an installation in a product boundary."""

    __tablename__ = "suite_product_installation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_code", name="uq_suite_installation_tenant_product"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    product_code: ProductCode = Field(sa_column=Column(String(32), nullable=False))
    local_identifier: str = Field(sa_column=Column(String(255), nullable=False))
    projection_endpoint: str | None = Field(default=None, max_length=2048)
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    workload_key_id: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, index=True))
    workload_public_key: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    workload_key_status: str = Field(default="UNCONFIGURED", max_length=32, index=True)
    workload_key_valid_from: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    workload_key_valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    workload_key_version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SuiteProjectionOutbox(SQLModel, table=True):
    """An immutable, retryable projection intent owned by the suite control plane."""

    __tablename__ = "suite_projection_outbox"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "projection_kind",
            "projection_version",
            name="uq_suite_projection_installation_kind_version",
        ),
        Index("ix_suite_projection_outbox_status_next_attempt", "status", "next_attempt_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, nullable=False, unique=True, index=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    installation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_product_installation.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    projection_kind: str = Field(sa_column=Column(String(64), nullable=False))
    projection_version: int = Field(nullable=False)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    payload_digest: str = Field(sa_column=Column(String(64), nullable=False))
    status: str = Field(default="PENDING", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    next_attempt_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    acknowledgement_receipt: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    dead_letter_reason: str | None = Field(default=None, max_length=1000)
    last_error: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class SuiteProjectionAttempt(SQLModel, table=True):
    """Immutable operational evidence for each projection delivery decision."""

    __tablename__ = "suite_projection_attempt"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    projection_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_projection_outbox.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    attempt_number: int = Field(nullable=False)
    outcome: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    http_status: int | None = Field(default=None, nullable=True)
    error_code: str | None = Field(default=None, max_length=1000)
    recorded_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class NativeProjectionCursor(SQLModel, table=True):
    """Last successfully applied projection version for an installation."""

    __tablename__ = "native_projection_cursor"
    __table_args__ = (UniqueConstraint("installation_id", name="uq_native_projection_cursor_installation"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    installation_id: uuid.UUID = Field(sa_column=Column(ForeignKey("suite_product_installation.id", ondelete="CASCADE"), nullable=False, index=True))
    cursor: str | None = Field(default=None, max_length=255)
    projection_version: int = Field(default=0, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class NativeProjectionReceipt(SQLModel, table=True):
    """Idempotent receipt for a projected mutation."""

    __tablename__ = "native_projection_receipt"
    __table_args__ = (UniqueConstraint("installation_id", "event_id", name="uq_native_projection_receipt_event"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    installation_id: uuid.UUID = Field(sa_column=Column(ForeignKey("suite_product_installation.id", ondelete="CASCADE"), nullable=False, index=True))
    event_id: uuid.UUID = Field(nullable=False, index=True)
    payload_digest: str = Field(max_length=64)
    acknowledged_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ProjectionDispatchEvent(SQLModel, table=True):
    """Durable native-projection work item scoped to one installation."""

    __tablename__ = "projection_dispatch_event"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "idempotency_key",
            name="uq_projection_dispatch_installation_idempotency",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    installation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_product_installation.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    event_type: str = Field(sa_column=Column(String(128), nullable=False))
    payload: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    idempotency_key: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(default="PENDING", max_length=32, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    available_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    lease_token: uuid.UUID | None = Field(default=None, nullable=True, index=True)
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True, index=True)
    )
    last_error: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
    acknowledged_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    dead_lettered_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class NativeWorkloadReplay(SQLModel, table=True):
    """Consumed assertion JTIs, scoped to their originating installation."""

    __tablename__ = "native_workload_replay"
    __table_args__ = (UniqueConstraint("installation_id", "jti", name="uq_native_workload_replay_installation_jti"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    installation_id: uuid.UUID = Field(sa_column=Column(ForeignKey("suite_product_installation.id", ondelete="CASCADE"), nullable=False, index=True))
    jti: uuid.UUID = Field(nullable=False, index=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    consumed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SupportAccessGrant(SQLModel, table=True):
    """Time-bounded, tenant-scoped support authority."""

    __tablename__ = "suite_support_access_grant"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("suite_tenant.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    operator_user_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    reason: str = Field(sa_column=Column(String(500), nullable=False))
    ticket_reference: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    approved_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id"), nullable=True))
    starts_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
