"""Tenant control-plane persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class ProductCode(str, Enum):
    COMMIT_ARC = "commitarc"
    REVENUE_OS = "revenueos"
    SIGNAL_LOOP = "signalloop"


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
