"""Workspace and workspace membership persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    """Return datetime utc."""
    return datetime.now(timezone.utc)


class Workspace(SQLModel, table=True):
    """A tenant/workspace boundary for SignalLoop data."""

    __tablename__ = "workspaces"

    id: str = Field(sa_column=Column(String(64), primary_key=True))
    display_name: str = Field(default="Workspace", max_length=255)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class WorkspaceMembership(SQLModel, table=True):
    """A user's role in one workspace.

    Roles are stored as strings to avoid database enum churn as product roles
    evolve. Authorization code centralizes which strings satisfy each surface.
    """

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_workspace_user"),
        Index("idx_workspace_membership_user", "user_id"),
        Index("idx_workspace_membership_workspace", "workspace_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    role: str = Field(default="operator", max_length=50, index=True)
    status: str = Field(default="active", max_length=32, index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
