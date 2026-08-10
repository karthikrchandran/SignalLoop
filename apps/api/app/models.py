# ruff: noqa: E402, F401, I001
"""Persistence + API models for the ``app`` domain."""

import uuid
from datetime import datetime, timezone

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    """Return datetime utc."""
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    """User base."""
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="operator", max_length=50)


# Properties to receive via API on creation
class UserCreate(UserBase):
    """Request payload for creating user."""
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    """User register."""
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    """Request payload for updating user."""
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    """User update me."""
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    """Update password."""
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    """User."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    auth_session_version: int = Field(default=1, ge=1, nullable=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    """API response model: user."""
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    """API response model: users."""
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    """Message."""
    message: str


# JSON payload containing access token
class Token(SQLModel):
    """Token row: token."""
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    """Token payload."""
    sub: str | None = None


class NewPassword(SQLModel):
    """New password."""
    token: str
    new_password: str = Field(min_length=8, max_length=128)


from app.domain_models import (  # noqa: E402
    Account,
    Campaign,
    CampaignChannelStrategy,
    CampaignContactImport,
    CampaignContactStage,
    CampaignPolicyBinding,
    CampaignSegment,
    CampaignSegmentRule,
    GlobalControlState,
    GovernancePolicy,
    OfferPack,
    OfferPackTemplateBinding,
    OfferPackVersion,
    ProspectingSnapshot,
    Template,
    TemplateToken,
    TemplateVersion,
    ContactEvent,
    RoutingDecision,
)

from app.domain.identity.models import OidcIdentity, OidcSession  # noqa: E402, F401
from app.domain.tenants.models import (  # noqa: E402, F401
    NativeProjectionCursor,
    NativeProjectionReceipt,
    NativeWorkloadReplay,
    ProductInstallation,
    SuiteMembership,
    SuiteRoleAssignment,
    SupportAccessGrant,
    Tenant,
    TenantEntitlement,
    TenantInvitation,
)
from app.domain.branding.models import (  # noqa: E402, F401
    TenantBrandAsset,
    TenantBrandingVersion,
)

from app.domain.audit.audit_events import AuditEvent  # noqa: E402
from app.domain.sequences.models import (  # noqa: E402
    ContactSequenceState,
    EmailEvent,
    EmailSequence,
    SendRequest,
    SequenceStep,
)
from app.domain.sequences.suppression import EmailSuppression  # noqa: E402
from app.domain.signals.models import SignalEvent  # noqa: E402
from app.domain.voice.models import CallRequest, CallSession, VoiceScript  # noqa: E402
from app.domain.signals.scheduling import SchedulingRequest  # noqa: E402
from app.domain.workspaces.models import Workspace, WorkspaceMembership  # noqa: E402
from app.domain.chatbot.models import (  # noqa: E402
    ChatbotAnalyticsSnapshot,
    ChatbotBotConfig,
    ChatbotChannelConfig,
    ChatbotConversation,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeSource,
    ChatbotMessage,
    ChatbotOptOut,
)
