"""Persistence + API models for the ``app`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Synonym, synonym
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    """Return datetime utc."""
    return datetime.now(timezone.utc)


class CampaignStatus(str, Enum):
    """Enumeration of campaign states."""

    draft = "draft"
    active = "active"
    paused = "paused"


class TemplateStatus(str, Enum):
    """Enumeration of template states."""

    draft = "draft"
    published = "published"
    archived = "archived"


class PolicyStatus(str, Enum):
    """Enumeration of policy states."""

    active = "active"
    inactive = "inactive"


class PolicyType(str, Enum):
    """Enumeration of policy variants."""

    daily_caps = "daily_caps"
    quiet_hours = "quiet_hours"
    suppression = "suppression"


class ContactProgressionState(str, Enum):
    """Enumeration of contact progression states."""

    inbox = "inbox"
    nurturing = "nurturing"
    engaged = "engaged"
    replied = "replied"
    booked = "booked"
    handed_off = "handed_off"
    opted_out = "opted_out"


class NotificationProvider(str, Enum):
    """Enumeration of notification providers.

    New values must also be appended to the Postgres enum type
    via an Alembic migration using ``ALTER TYPE notificationprovider ADD VALUE``.
    """

    # --- email ---
    sendgrid = "sendgrid"
    smtp = "smtp"
    ses = "ses"
    postmark = "postmark"
    mailgun = "mailgun"
    brevo = "brevo"
    resend = "resend"
    # --- sms / voice ---
    twilio = "twilio"
    vapi = "vapi"
    # --- speech-to-text ---
    deepgram = "deepgram"
    whisper_api = "whisper_api"
    faster_whisper_local = "faster_whisper_local"
    # --- text-to-speech ---
    aura = "aura"
    elevenlabs = "elevenlabs"
    playht = "playht"
    polly = "polly"
    piper_local = "piper_local"
    coqui_local = "coqui_local"
    # --- llm ---
    groq = "groq"
    openai = "openai"
    anthropic = "anthropic"
    ollama_local = "ollama_local"
    together = "together"
    openrouter = "openrouter"
    gemini = "gemini"
    # --- chatbot channels ---
    facebook_messenger = "facebook_messenger"
    whatsapp_cloud = "whatsapp_cloud"
    telegram_bot = "telegram_bot"
    linkedin_redirect = "linkedin_redirect"
    # --- scheduling / other ---
    mailchimp = "mailchimp"
    calendly = "calendly"


class ProviderCapability(str, Enum):
    """Enumeration of provider capabilities a workspace can configure independently."""

    email = "email"
    sms = "sms"
    voice = "voice"
    stt = "stt"
    tts = "tts"
    llm = "llm"


class SegmentOperator(str, Enum):
    """Enumeration of segment comparison operators."""

    equals = "equals"
    contains = "contains"
    in_list = "in-list"
    starts_with = "startsWith"


class SemanticError(str, Enum):
    """Enumeration of semantic categories."""

    recipient_invalid = "RECIPIENT_INVALID"
    policy_violation = "POLICY_VIOLATION"
    auth_error = "AUTH_ERROR"
    system_error = "SYSTEM_ERROR"
    unknown_error = "UNKNOWN_ERROR"


class Campaign(SQLModel, table=True):
    """Campaign."""

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_campaign_id_workspace"),
        Index("idx_campaign_workspace_status", "workspace_id", "status"),
        Index("idx_campaign_workspace_created_by", "workspace_id", "created_by"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    status: CampaignStatus = Field(default=CampaignStatus.draft)
    created_by: uuid.UUID
    workspace_id: str = Field(sa_type=String(64), index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class CampaignContactImport(SQLModel, table=True):
    """Campaign contact import."""

    __tablename__ = "campaign_contact_imports"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    source_file_name: str = Field(max_length=255)
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    mapping_json: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    headers_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class CampaignContactStage(SQLModel, table=True):
    """Staging row: campaign contact."""

    __tablename__ = "campaign_contact_staging"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    import_id: uuid.UUID = Field(foreign_key="campaign_contact_imports.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    row_number: int
    is_valid: bool = False
    mapped_data_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    error_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class CampaignSegment(SQLModel, table=True):
    """Campaign segment."""

    __tablename__ = "campaign_segments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(max_length=255)
    estimated_count: int = 0
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class CampaignSegmentRule(SQLModel, table=True):
    """Rule row: campaign segment."""

    __tablename__ = "campaign_segment_rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    segment_id: uuid.UUID = Field(foreign_key="campaign_segments.id", index=True)
    field_name: str = Field(max_length=100)
    operator: SegmentOperator
    value: str = Field(sa_type=Text)
    expression_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )


class CampaignChannelStrategy(SQLModel, table=True):
    """Strategy row: campaign channel."""

    __tablename__ = "campaign_channel_strategy"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    offer_pack_id: uuid.UUID | None = Field(default=None, foreign_key="offer_packs.id")
    offer_pack_version_id: uuid.UUID | None = Field(
        default=None, foreign_key="offer_pack_versions.id"
    )
    strategy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class Template(SQLModel, table=True):
    """Template."""

    __tablename__ = "templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(max_length=255)
    channel: str = Field(max_length=32)
    created_by: uuid.UUID
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class TemplateVersion(SQLModel, table=True):
    """Version row: template."""

    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "version_number", name="uq_template_version_number"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(foreign_key="templates.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    version_number: int
    status: TemplateStatus = Field(default=TemplateStatus.draft)
    subject: str | None = Field(default=None, max_length=255)
    content: str = Field(sa_type=Text)
    guardrail_compliant: bool = False
    guardrail_report_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class TemplateToken(SQLModel, table=True):
    """Token row: template."""

    __tablename__ = "template_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(foreign_key="templates.id", index=True)
    name: str = Field(max_length=100)
    source_field: str = Field(max_length=100)
    default_value: str | None = Field(default=None, max_length=255)
    fallback_behavior: str = Field(default="defaultValue", max_length=50)


class OfferPack(SQLModel, table=True):
    """Offer pack."""

    __tablename__ = "offer_packs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(max_length=255)
    created_by: uuid.UUID
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class OfferPackVersion(SQLModel, table=True):
    """Version row: offer pack."""

    __tablename__ = "offer_pack_versions"
    __table_args__ = (
        UniqueConstraint(
            "offer_pack_id", "version_number", name="uq_offer_pack_version_number"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_pack_id: uuid.UUID = Field(foreign_key="offer_packs.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    version_number: int
    status: TemplateStatus = Field(default=TemplateStatus.draft)
    is_default: bool = False
    guardrail_compliant: bool = False
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class OfferPackTemplateBinding(SQLModel, table=True):
    """Binding row: offer pack template."""

    __tablename__ = "offer_pack_template_bindings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_pack_version_id: uuid.UUID = Field(
        foreign_key="offer_pack_versions.id", index=True
    )
    template_version_id: uuid.UUID = Field(
        foreign_key="template_versions.id", index=True
    )
    channel: str = Field(max_length=32)
    script_variant: str | None = Field(default=None, max_length=255)


class GovernancePolicy(SQLModel, table=True):
    """Policy row: governance."""

    __tablename__ = "governance_policies"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    campaign_id: uuid.UUID | None = Field(
        default=None, foreign_key="campaigns.id", index=True
    )
    scope: str = Field(max_length=32)
    policy_type: PolicyType
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: PolicyStatus = Field(default=PolicyStatus.active)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class CampaignPolicyBinding(SQLModel, table=True):
    """Binding row: campaign policy."""

    __tablename__ = "campaign_policy_bindings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    policy_id: uuid.UUID = Field(foreign_key="governance_policies.id", index=True)


class GlobalControlState(SQLModel, table=True):
    """Enumeration of global control states."""

    __tablename__ = "global_control_state"
    __table_args__ = (
        Index(
            "uq_global_control_state_workspace_global",
            "workspace_id",
            unique=True,
            postgresql_where=text("campaign_id IS NULL"),
        ),
        Index(
            "uq_global_control_state_workspace_campaign",
            "workspace_id",
            "campaign_id",
            unique=True,
            postgresql_where=text("campaign_id IS NOT NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    campaign_id: uuid.UUID | None = Field(
        default=None, foreign_key="campaigns.id", index=True
    )
    paused: bool = False
    paused_by: uuid.UUID | None = None
    paused_reason: str | None = Field(default=None, max_length=255)
    paused_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Epic 2 — Contact delivery pipeline foundation
# ---------------------------------------------------------------------------


class Account(SQLModel, table=True):
    """First-class customer account."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "account_key", name="uq_account_workspace_key"
        ),
        Index("idx_accounts_workspace_name", "workspace_id", "name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(sa_type=String(255))
    account_key: str = Field(sa_type=String(255), index=True)
    website_url: str | None = Field(default=None, sa_type=Text)
    industry: str | None = Field(default=None, max_length=255)
    status: str = Field(default="active", max_length=64)
    summary: str | None = Field(default=None, sa_type=Text)
    tags_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class Contact(SQLModel, table=True):
    """Contact."""

    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_contact_id_workspace"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    shared_account_id: uuid.UUID | None = Field(
        default=None,
        alias="account_id",
        sa_column=Column("account_id", Uuid(), index=True, nullable=True),
    )
    account_id: ClassVar[Synonym] = synonym("shared_account_id")
    email: str = Field(sa_type=String(255), index=True)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str = Field(default="UTC", max_length=64)
    source_channel: str | None = Field(default=None, max_length=64)
    tags_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    intent_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    consent_email: bool = Field(default=False, nullable=False)
    consent_voice: bool = Field(default=False, nullable=False)
    do_not_contact: bool = Field(default=False, nullable=False)
    suppressed: bool = Field(default=False, nullable=False)
    last_seen_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class ProspectingSnapshot(SQLModel, table=True):
    """Persisted prospecting research result for one contact."""

    __tablename__ = "prospecting_snapshots"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    created_by: uuid.UUID | None = Field(default=None, index=True)
    company_url: str | None = Field(default=None, sa_type=Text)
    sources_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    research_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    email_draft: str = Field(sa_type=Text)
    voice_opener: str = Field(sa_type=Text)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True), index=True
    )


class ContactProgression(SQLModel, table=True):
    """Tracks the current delivery-pipeline state for one contact within a campaign."""

    __tablename__ = "contact_progression"
    __table_args__ = (
        UniqueConstraint(
            "contact_id",
            "campaign_id",
            name="uq_contact_progression_contact_campaign",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    current_state: ContactProgressionState
    last_action_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class ContactStateHistory(SQLModel, table=True):
    """Immutable audit trail of every state transition for a contact."""

    __tablename__ = "contact_state_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    from_state: ContactProgressionState
    to_state: ContactProgressionState
    reason: str | None = Field(default=None, max_length=255)
    triggered_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class OutboxEvent(SQLModel, table=True):
    """Transactional outbox for reliable at-least-once event publishing."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_outbox_workspace_idempotency",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    aggregate_id: uuid.UUID = Field(index=True)
    aggregate_type: str = Field(max_length=64)  # "contact" | "campaign"
    event_type: str = Field(max_length=128)  # "contact.progressed" | "action.queued"
    event_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    idempotency_key: str = Field(max_length=255, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class IdempotencyRecord(SQLModel, table=True):
    """Durable claim and replay record for HTTP mutations."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_workspace_operation_key",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    operation: str = Field(max_length=128)
    idempotency_key: str = Field(max_length=255)
    request_hash: str = Field(max_length=64)
    state: str = Field(default="in_progress", max_length=32)
    response_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    failure_reason: str | None = Field(default=None, max_length=128)
    lease_expires_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class ActionQueue(SQLModel, table=True):
    """Work item for the delivery worker — one outbound action per row."""

    __tablename__ = "action_queue"
    __table_args__ = (
        ForeignKeyConstraint(
            ["campaign_id", "workspace_id"],
            ["campaigns.id", "campaigns.workspace_id"],
            name="fk_action_queue_campaign_workspace",
        ),
        ForeignKeyConstraint(
            ["contact_id", "workspace_id"],
            ["contacts.id", "contacts.workspace_id"],
            name="fk_action_queue_contact_workspace",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(max_length=64, index=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    action_type: str = Field(max_length=64)  # "send_email" | "make_call" | "send_sms"
    channel: str = Field(max_length=32)  # "email" | "phone" | "sms"
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending", max_length=32, index=True)
    retry_count: int = Field(default=0)
    failure_reason: str | None = Field(default=None, sa_type=Text)
    next_retry_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), index=True
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    executed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    dead_lettered_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )


class ProviderCredential(SQLModel, table=True):
    """Per-workspace provider API credentials (stored encrypted at rest)."""

    __tablename__ = "provider_credentials"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    provider: NotificationProvider
    channel: str = Field(max_length=32)  # "email" | "sms" | "voice" | "scheduling"
    encrypted_api_key: str = Field(sa_type=Text)
    encrypted_api_secret: str | None = Field(default=None, sa_type=Text)
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class WorkspaceRuntimeConfig(SQLModel, table=True):
    """Per-workspace runtime settings that do not fit provider-credential storage."""

    __tablename__ = "workspace_runtime_configs"

    workspace_id: str = Field(primary_key=True, sa_type=String(64))
    encrypted_deepgram_api_key: str | None = Field(default=None, sa_type=Text)
    encrypted_groq_api_key: str | None = Field(default=None, sa_type=Text)
    team_notification_email: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class WorkspaceProviderSelection(SQLModel, table=True):
    """Per-workspace active provider choice for a given capability.

    Workspaces use this to opt out of the default provider (Twilio/SendGrid/etc.)
    and route a capability (email/sms/voice/stt/tts/llm) to an alternate.
    Credentials still live in ``provider_credentials``.
    """

    __tablename__ = "workspace_provider_selections"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "capability",
            name="uq_workspace_provider_selection_capability",
        ),
        Index("idx_wps_workspace", "workspace_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    capability: ProviderCapability
    provider: NotificationProvider
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class WorkerHeartbeat(SQLModel, table=True):
    """Last-known liveness and error status for each long-running worker."""

    __tablename__ = "worker_heartbeats"

    worker_key: str = Field(primary_key=True, max_length=64)
    status: str = Field(default="starting", max_length=32)
    poll_interval_seconds: int = Field(default=30)
    last_seen_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True), index=True
    )
    last_success_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    last_error_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    last_error_message: str | None = Field(default=None, sa_type=Text)
    last_processed_count: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class ProviderEventLog(SQLModel, table=True):
    """Normalised inbound webhook events from external notification providers."""

    __tablename__ = "provider_event_logs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider",
            "provider_event_id",
            name="uq_provider_event_workspace_provider_event_id",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    provider: NotificationProvider
    provider_event_id: str = Field(max_length=255, index=True)
    event_type: str = Field(max_length=128)  # "bounce" | "delivered" | "opened"
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    normalized_event: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    received_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


# ---------------------------------------------------------------------------
# Epic 5 — Contact Timeline & Explainability
# ---------------------------------------------------------------------------


class ContactEvent(SQLModel, table=True):
    """Immutable event store for all contact lifecycle events within a campaign."""

    __tablename__ = "contact_events"
    __table_args__ = (
        Index("idx_ce_contact_campaign", "contact_id", "campaign_id"),
        Index("idx_ce_workspace_type", "workspace_id", "event_type"),
        Index("idx_ce_created_at", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    event_type: str = Field(max_length=128)
    channel: str | None = Field(default=None, max_length=32)
    actor: str | None = Field(default=None, max_length=128)
    outcome: str | None = Field(default=None, max_length=128)
    reason_code: str | None = Field(default=None, max_length=255)
    rule_ref: str | None = Field(default=None, max_length=255)
    template_ref: str | None = Field(default=None, max_length=255)
    confidence_tier: str | None = Field(default=None, max_length=32)
    event_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, name="metadata")
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class RoutingDecision(SQLModel, table=True):
    """Stores automated routing/sequencing decisions for explainability."""

    __tablename__ = "routing_decisions"
    __table_args__ = (
        Index("idx_rd_contact_campaign", "contact_id", "campaign_id"),
        Index("idx_rd_workspace", "workspace_id"),
        Index("idx_rd_created_at", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    decision_type: str = Field(max_length=128)
    outcome: str | None = Field(default=None, max_length=128)
    reason_code: str | None = Field(default=None, max_length=255)
    rule_name: str | None = Field(default=None, max_length=255)
    rule_condition: str | None = Field(default=None, sa_type=Text)
    signal_summary: str | None = Field(default=None, sa_type=Text)
    confidence_tier: str | None = Field(default=None, max_length=32)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


# ---------------------------------------------------------------------------
# Epic 5 Story 4 — KPI Daily Snapshots (materialized aggregation table)
# ---------------------------------------------------------------------------


class KpiDailySnapshot(SQLModel, table=True):
    """Materialized daily KPI aggregation — populated by the nightly snapshot job."""

    __tablename__ = "kpi_daily_snapshots"
    __table_args__ = (
        Index("idx_kpi_snapshots_workspace_date", "workspace_id", "date"),
        Index(
            "idx_kpi_snapshots_workspace_campaign_date",
            "workspace_id",
            "campaign_id",
            "date",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    date: datetime = Field(
        sa_type=DateTime(timezone=False)
    )  # DATE stored as datetime at midnight UTC
    workspace_id: str = Field(sa_type=String(64), index=True)
    campaign_id: uuid.UUID | None = Field(
        default=None, foreign_key="campaigns.id", index=True
    )
    contacts_processed: int = Field(default=0)
    intent_signals: int = Field(default=0)
    qualified_contacts: int = Field(default=0)
    bookings_confirmed: int = Field(default=0)
    provider_errors: int = Field(default=0)
    booking_sla_met: int = Field(default=0)
    booking_sla_breached: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class ImportRowError(SQLModel):
    """Enumeration of import row categories."""

    row_number: int
    column: str
    semantic_error: SemanticError
    message: str


class PreviewRow(SQLModel):
    """Preview row."""

    row_number: int
    data: dict[str, Any]


class HealthStatus(SQLModel):
    """Enumeration of health states."""

    api: bool
    postgres: bool
    redis: bool


class CampaignCreate(SQLModel):
    """Request payload for creating campaign."""

    name: str


class CampaignPublic(SQLModel):
    """API response model: campaign."""

    id: uuid.UUID
    name: str
    status: CampaignStatus
    workspace_id: str
    created_at: datetime


class CampaignsPublic(SQLModel):
    """API response model: campaigns."""

    data: list[CampaignPublic]
    count: int


class ContactPublic(SQLModel):
    """API response model: contact."""

    id: uuid.UUID
    workspace_id: str
    account_id: uuid.UUID | None = None
    email: str
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    phone: str | None = None
    timezone: str
    source_channel: str | None = None
    tags_json: list[str] = Field(default_factory=list)
    intent_json: list[str] = Field(default_factory=list)
    consent_email: bool = False
    consent_voice: bool = False
    do_not_contact: bool = False
    suppressed: bool = False
    last_seen_at: datetime | None = None
    created_at: datetime


class AccountPublic(SQLModel):
    """API response model: account."""

    id: uuid.UUID
    workspace_id: str
    name: str
    account_key: str
    website_url: str | None = None
    industry: str | None = None
    status: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AccountCreate(SQLModel):
    """Request payload for creating an account."""

    name: str = Field(min_length=1, max_length=255)
    website_url: str | None = None
    industry: str | None = Field(default=None, max_length=255)
    status: str = Field(default="active", max_length=64)
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)


class AccountUpdate(SQLModel):
    """Request payload for updating account metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    website_url: str | None = None
    industry: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=64)
    summary: str | None = None
    tags: list[str] | None = None


class AccountContactAssignment(SQLModel):
    """Request payload for assigning contacts to an account."""

    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class AccountContactAssignmentPublic(SQLModel):
    """API response model: account contact assignment result."""

    account_id: uuid.UUID
    assigned_count: int = 0
    unassigned_count: int = 0
    contact_ids: list[uuid.UUID] = Field(default_factory=list)


class Customer360AccountRowPublic(AccountPublic):
    """Customer 360 account list row."""

    contact_count: int
    last_activity_at: datetime | None = None
    channel_counts: dict[str, int] = Field(default_factory=dict)
    top_next_action: str | None = None


class Customer360AccountsPublic(SQLModel):
    """Customer 360 account list response."""

    data: list[Customer360AccountRowPublic] = Field(default_factory=list)
    count: int


class Customer360ContactPublic(ContactPublic):
    """Contact shown inside a Customer 360 account."""

    display_name: str


class Customer360ChannelSummaryPublic(SQLModel):
    """One channel summary card."""

    channel: str
    label: str
    count: int
    status: str
    detail: str


class Customer360NextActionPublic(SQLModel):
    """Recommended account-level follow-up."""

    title: str
    reason: str
    source: str
    priority: str


class Customer360OpenWorkPublic(SQLModel):
    """Open work item for an account."""

    id: str
    source: str
    title: str
    contact_id: uuid.UUID | None = None
    contact_name: str | None = None
    status: str
    created_at: datetime


class Customer360ProspectingBriefPublic(SQLModel):
    """Latest prospecting brief for an account."""

    snapshot_id: uuid.UUID
    contact_id: uuid.UUID
    account_summary: str
    suggested_next_action: str | None = None
    email_draft_available: bool
    voice_opener_available: bool
    created_at: datetime


class Customer360TimelineEventPublic(SQLModel):
    """Account-level timeline event."""

    id: str
    source: str
    event_type: str
    title: str
    detail: str
    contact_id: uuid.UUID | None = None
    contact_name: str | None = None
    timestamp: datetime


class Customer360AccountProfilePublic(SQLModel):
    """Full Account Command Center payload."""

    account: AccountPublic
    contacts: list[Customer360ContactPublic] = Field(default_factory=list)
    channel_summaries: dict[str, Customer360ChannelSummaryPublic] = Field(
        default_factory=dict,
    )
    next_best_action: Customer360NextActionPublic | None = None
    open_work: list[Customer360OpenWorkPublic] = Field(default_factory=list)
    prospecting_brief: Customer360ProspectingBriefPublic | None = None
    timeline: list[Customer360TimelineEventPublic] = Field(default_factory=list)


class ContactsPublic(SQLModel):
    """API response model: contacts."""

    data: list[ContactPublic]
    count: int


class ContactImportPublic(SQLModel):
    """API response model: canonical contact import."""

    total_rows: int
    valid_rows: int
    invalid_rows: int
    created_count: int = 0
    updated_count: int = 0
    committed: bool = False
    requires_mapping: bool
    headers: list[str]
    mapping: dict[str, str]
    preview_rows: list[PreviewRow]
    errors: list[ImportRowError]


class CampaignAudiencePublic(SQLModel):
    """API response model: campaign audience assignment."""

    campaign_id: uuid.UUID
    selected_count: int
    added_count: int
    existing_count: int
    segment_id: uuid.UUID | None = None
    segment_name: str | None = None


class CampaignImportPublic(SQLModel):
    """API response model: campaign import."""

    import_id: uuid.UUID
    total_rows: int
    valid_rows: int
    invalid_rows: int
    requires_mapping: bool
    headers: list[str]
    errors: list[ImportRowError]


class CampaignMappingRequest(SQLModel):
    """Request payload: campaign mapping."""

    mapping: dict[str, str]


class ImportPreviewPublic(SQLModel):
    """API response model: import preview."""

    import_id: uuid.UUID
    preview_rows: list[PreviewRow]
    errors: list[ImportRowError]


class SegmentRuleInput(SQLModel):
    """Input payload: segment rule."""

    field_name: str
    operator: SegmentOperator
    value: str


class CampaignAudienceRequest(SQLModel):
    """Request payload for assigning existing contacts to a campaign."""

    include_all_contacts: bool = False
    contact_ids: list[uuid.UUID] = Field(default_factory=list)
    segment_name: str | None = None
    rules: list[SegmentRuleInput] = Field(default_factory=list)


class CampaignSegmentCreate(SQLModel):
    """Request payload for creating campaign segment."""

    name: str
    rules: list[SegmentRuleInput]


class CampaignSegmentPublic(SQLModel):
    """API response model: campaign segment."""

    id: uuid.UUID
    name: str
    estimated_count: int


class StrategyRequest(SQLModel):
    """Request payload: strategy."""

    offer_pack_id: uuid.UUID | None = None
    offer_pack_version_id: uuid.UUID | None = None
    channel_strategy: dict[str, Any] = Field(default_factory=dict)


class StrategyPublic(SQLModel):
    """API response model: strategy."""

    id: uuid.UUID
    campaign_id: uuid.UUID
    strategy_json: dict[str, Any]


class TokenDefinition(SQLModel):
    """Definition: token."""

    name: str
    source_field: str
    default_value: str | None = None
    fallback_behavior: str = "defaultValue"


class TemplateCreate(SQLModel):
    """Request payload for creating template."""

    name: str
    channel: str
    subject: str | None = None
    content: str
    tokens: list[TokenDefinition] = Field(default_factory=list)


class TemplateUpdate(SQLModel):
    """Request payload for updating template."""

    name: str | None = None
    subject: str | None = None
    content: str | None = None
    tokens: list[TokenDefinition] | None = None


class GuardrailViolation(SQLModel):
    """Guardrail violation."""

    semantic_error: SemanticError
    reason_code: str
    message: str


class TemplateVersionPublic(SQLModel):
    """API response model: template version."""

    id: uuid.UUID
    version_number: int
    status: TemplateStatus
    guardrail_compliant: bool
    content: str
    subject: str | None = None


class TemplatePublic(SQLModel):
    """API response model: template."""

    id: uuid.UUID
    name: str
    channel: str
    workspace_id: str
    current_version: TemplateVersionPublic | None = None


class TemplatesPublic(SQLModel):
    """API response model: templates."""

    data: list[TemplatePublic]
    count: int


class TemplatePreviewRequest(SQLModel):
    """Request payload: template preview."""

    sample_payload: dict[str, Any] = Field(default_factory=dict)


class TemplatePreviewPublic(SQLModel):
    """API response model: template preview."""

    rendered_content: str
    unresolved_tokens: list[str]


class OfferPackBindingInput(SQLModel):
    """Input payload: offer pack binding."""

    template_version_id: uuid.UUID
    channel: str
    script_variant: str | None = None


class OfferPackCreate(SQLModel):
    """Request payload for creating offer pack."""

    name: str
    bindings: list[OfferPackBindingInput] = Field(default_factory=list)
    is_default: bool = False


class OfferPackVersionCreate(SQLModel):
    """Request payload for creating offer pack version."""

    bindings: list[OfferPackBindingInput] = Field(default_factory=list)
    is_default: bool = False


class OfferPackVersionPublic(SQLModel):
    """API response model: offer pack version."""

    id: uuid.UUID
    version_number: int
    status: TemplateStatus
    is_default: bool
    guardrail_compliant: bool


class OfferPackPublic(SQLModel):
    """API response model: offer pack."""

    id: uuid.UUID
    name: str
    workspace_id: str
    current_version: OfferPackVersionPublic | None = None


class OfferPacksPublic(SQLModel):
    """API response model: offer packs."""

    data: list[OfferPackPublic]
    count: int


class GovernancePolicyCreate(SQLModel):
    """Request payload for creating governance policy."""

    scope: str
    policy_type: PolicyType
    campaign_id: uuid.UUID | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyPublic(SQLModel):
    """API response model: governance policy."""

    id: uuid.UUID
    scope: str
    policy_type: PolicyType
    status: PolicyStatus
    payload_json: dict[str, Any]


class GovernancePoliciesPublic(SQLModel):
    """API response model: governance policies."""

    data: list[GovernancePolicyPublic]
    count: int


class PolicyDecision(SQLModel):
    """Decision row: policy."""

    allowed: bool
    semantic_error: SemanticError | None = None
    reason_code: str | None = None
    next_eligible_at: datetime | None = None


class PolicyEvaluationRequest(SQLModel):
    """Request payload: policy evaluation."""

    campaign_id: uuid.UUID | None = None
    contact: dict[str, Any] = Field(default_factory=dict)
    campaign_daily_count: int = 0
    system_daily_count: int = 0
    requested_at: datetime | None = None


class PauseRequest(SQLModel):
    """Request payload: pause."""

    paused_reason: str


class ControlStatePublic(SQLModel):
    """API response model: control state."""

    id: uuid.UUID
    paused: bool
    paused_reason: str | None = None
    paused_at: datetime | None = None
    action: str
    actor_id: uuid.UUID | None = None
    actor_role: str
    action_at: datetime


# ---------------------------------------------------------------------------
# Epic 5 — Contact Timeline public schemas
# ---------------------------------------------------------------------------


class TimelineEventPublic(SQLModel):
    """Unified timeline entry returned by the aggregation API."""

    id: str  # prefixed: "csh_<uuid>", "ce_<uuid>", "rd_<uuid>"
    source_system: (
        str  # "contact_state_history" | "contact_events" | "routing_decisions"
    )
    event_type: str
    channel: str | None = None
    timestamp: datetime
    actor: str | None = None
    outcome: str | None = None
    reason_code: str | None = None
    rule_ref: str | None = None
    template_ref: str | None = None
    confidence_tier: str | None = None
    has_detail: bool = False


class TimelineEventDetailPublic(TimelineEventPublic):
    """Extended timeline entry with explainability fields."""

    reason_code_explanation: str | None = None
    rule_name: str | None = None
    rule_condition: str | None = None
    signal_summary: str | None = None
    transcript_excerpt: str | None = None


class TimelinePagePublic(SQLModel):
    """API response model: timeline page."""

    data: list[TimelineEventPublic]
    count: int
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Story 5.2 — Audit trail public schemas
# ---------------------------------------------------------------------------


class AuditEventPublic(SQLModel):
    """API response model: audit event."""

    id: uuid.UUID
    event_name: str
    workspace_id: str
    actor_id: uuid.UUID | None = None
    actor_role: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = {}
    created_at: datetime


class AuditEventsPage(SQLModel):
    """Audit events page."""

    total: int
    page: int
    limit: int
    items: list[AuditEventPublic]


class AuditExportJobStatus(SQLModel):
    """Enumeration of audit export job states."""

    job_id: str
    status: str  # "pending" | "complete" | "failed"


# ---------------------------------------------------------------------------
# Story 5.3 — Campaign health & dead-letter visibility
# ---------------------------------------------------------------------------


class DeadLetterEvent(SQLModel, table=True):
    """Immutable event log for dead-letter lifecycle (written synchronously for NFR8 SLA)."""

    __tablename__ = "dead_letter_events"
    __table_args__ = (
        Index("idx_dle_campaign_id", "campaign_id"),
        Index("idx_dle_action_queue_id", "action_queue_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    action_queue_id: uuid.UUID = Field(foreign_key="action_queue.id", index=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    shared_contact_id: uuid.UUID = Field(
        alias="contact_id",
        sa_column=Column("contact_id", Uuid(), index=True, nullable=False),
    )
    contact_id: ClassVar[Synonym] = synonym("shared_contact_id")
    workspace_id: str = Field(sa_type=String(64), index=True)
    action_type: str = Field(max_length=64)
    failure_reason: str | None = Field(default=None, sa_type=Text)
    event_type: str = Field(
        default="dead_lettered", max_length=32
    )  # dead_lettered|retried|dismissed
    operator_id: uuid.UUID | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


# --- Public schemas ---


class DeadLetterItemPublic(SQLModel):
    """Single dead-letter queue entry returned by the API."""

    id: uuid.UUID
    contact_id: uuid.UUID
    action_type: str
    failure_reason: str | None
    retry_count: int
    first_failed_at: datetime
    retry_eligible: bool


class DeadLetterListPublic(SQLModel):
    """API response model: dead letter list."""

    data: list[DeadLetterItemPublic]
    count: int
    page: int


class CampaignHealthPublic(SQLModel):
    """Live campaign health snapshot (Redis-cached, TTL 30 s)."""

    active_count: int
    success_count_1h: int
    success_count_24h: int
    failure_count_24h: int
    dead_letter_count: int
    provider_errors_by_type: dict[str, int]


from app.domain.shared_records.models import (  # noqa: E402, F401
    PlatformExternalLink,  # noqa: F401
    PlatformSharedAccount,  # noqa: F401
    PlatformSharedContact,  # noqa: F401
)
