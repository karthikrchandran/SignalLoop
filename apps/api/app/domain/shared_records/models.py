from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint
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
    workspace_id: str = Field(sa_type=String(64), index=True)
    external_key: str = Field(sa_type=String(255), index=True, unique=True)
    display_name: str = Field(sa_type=String(255))
    status: str = Field(default="active", sa_type=String(32))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )


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
    workspace_id: str = Field(sa_type=String(64), index=True)
    external_key: str = Field(sa_type=String(255), index=True, unique=True)
    parent_account_id: uuid.UUID | None = Field(default=None)
    display_name: str = Field(sa_type=String(255))
    email: str = Field(sa_type=String(255), index=True)
    phone: str | None = Field(default=None, sa_type=String(64))
    status: str = Field(default="active", sa_type=String(32))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )


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
    entity_type: str = Field(sa_type=String(32), index=True)
    entity_id: uuid.UUID = Field(index=True)
    source_app: str = Field(sa_type=String(32), index=True)
    source_record_id: str = Field(sa_type=String(255), index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )
