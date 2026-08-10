"""Tenant control-plane persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint
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
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


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
