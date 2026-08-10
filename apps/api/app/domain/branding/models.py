from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class BrandingLifecycle(str, Enum):
    DRAFT = "DRAFT"
    PREVIEWED = "PREVIEWED"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"


class BrandAssetKind(str, Enum):
    LOGO = "LOGO"
    HERO = "HERO"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TenantBrandingVersion(SQLModel, table=True):
    __tablename__ = "tenant_branding_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_branding_tenant_version"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    version: int = Field(default=1, nullable=False)
    lifecycle: BrandingLifecycle = Field(
        default=BrandingLifecycle.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    display_name: str = Field(sa_column=Column(String(80), nullable=False))
    product_name: str | None = Field(
        default=None, sa_column=Column(String(80), nullable=True)
    )
    headline: str = Field(sa_column=Column(String(120), nullable=False))
    supporting_copy: str = Field(sa_column=Column(String(300), nullable=False))
    primary_color: str = Field(
        default="#111827", sa_column=Column(String(7), nullable=False)
    )
    secondary_color: str = Field(
        default="#ffffff", sa_column=Column(String(7), nullable=False)
    )
    support_url: str | None = Field(
        default=None, sa_column=Column(String(2048), nullable=True)
    )
    privacy_url: str | None = Field(
        default=None, sa_column=Column(String(2048), nullable=True)
    )
    legal_url: str | None = Field(
        default=None, sa_column=Column(String(2048), nullable=True)
    )
    logo_asset_id: uuid.UUID | None = Field(default=None, nullable=True)
    hero_asset_id: uuid.UUID | None = Field(default=None, nullable=True)
    created_by: uuid.UUID | None = Field(default=None, nullable=True)
    validated_by: uuid.UUID | None = Field(default=None, nullable=True)
    published_by: uuid.UUID | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    published_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class TenantBrandAsset(SQLModel, table=True):
    __tablename__ = "tenant_brand_asset"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    kind: BrandAssetKind = Field(
        default=BrandAssetKind.LOGO, sa_column=Column(String(16), nullable=False)
    )
    mime_type: str = Field(sa_column=Column(String(64), nullable=False))
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    byte_count: int = Field(nullable=False)
    sha256: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    created_by: uuid.UUID | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
