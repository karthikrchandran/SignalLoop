from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformSharedAccount(SQLModel, table=True):
    __tablename__ = "platform_shared_accounts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_platform_shared_accounts_workspace_id_id",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    external_key: str = Field(sa_column=Column(String(255), nullable=False, index=True, unique=True))
    display_name: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(32), nullable=False, default="active"))
    account_key: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, default=None))
    website_url: str | None = Field(default=None, sa_type=Text)
    industry: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, default=None))
    summary: str | None = Field(default=None, sa_type=Text)
    tags_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))


class PlatformSharedContact(SQLModel, table=True):
    __tablename__ = "platform_shared_contacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "parent_account_id"],
            ["platform_shared_accounts.workspace_id", "platform_shared_accounts.id"],
            name="fk_platform_shared_contacts_workspace_parent_account",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    external_key: str = Field(sa_column=Column(String(255), nullable=False, index=True, unique=True))
    parent_account_id: uuid.UUID | None = Field(default=None)
    display_name: str = Field(sa_column=Column(String(255), nullable=False))
    email: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    phone: str | None = Field(default=None, sa_column=Column(String(64), nullable=True, default=None))
    company_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, default=None))
    first_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, default=None))
    last_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, default=None))
    timezone: str = Field(default="UTC", sa_column=Column(String(64), nullable=False, default="UTC"))
    source_channel: str | None = Field(default=None, sa_column=Column(String(64), nullable=True, default=None))
    tags_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    intent_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    last_seen_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True, default=None))
    status: str = Field(default="active", sa_column=Column(String(32), nullable=False, default="active"))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))


class PlatformSharedIdentity(SQLModel, table=True):
    """Canonical platform identity for shared lead and order records.

    Workflow-specific lead and order details remain in Sales Ops.  This model
    establishes the stable, cross-application identity required by the
    platform foundation.
    """

    __tablename__ = "platform_shared_identities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "entity_type",
            "external_key",
            name="uq_platform_shared_identities_workspace_type_key",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    entity_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    external_key: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    display_name: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(32), nullable=False, default="active"))
    data_json: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))


class PlatformExternalLink(SQLModel, table=True):
    __tablename__ = "platform_external_links"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "entity_type",
            "source_app",
            "source_record_id",
            name="uq_platform_external_links_source_identity",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    entity_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    entity_id: uuid.UUID = Field(index=True)
    source_app: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    source_record_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, default=utc_now))
