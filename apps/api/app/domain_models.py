from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class CampaignStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"


class TemplateStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class PolicyStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class PolicyType(str, Enum):
    daily_caps = "daily_caps"
    quiet_hours = "quiet_hours"
    suppression = "suppression"


class ContactProgressionState(str, Enum):
    inbox = "inbox"
    nurturing = "nurturing"
    engaged = "engaged"
    replied = "replied"
    booked = "booked"
    handed_off = "handed_off"
    opted_out = "opted_out"


class NotificationProvider(str, Enum):
    sendgrid = "sendgrid"
    twilio = "twilio"
    mailchimp = "mailchimp"
    calendly = "calendly"


class SegmentOperator(str, Enum):
    equals = "equals"
    contains = "contains"
    in_list = "in-list"
    starts_with = "startsWith"


class SemanticError(str, Enum):
    recipient_invalid = "RECIPIENT_INVALID"
    policy_violation = "POLICY_VIOLATION"
    auth_error = "AUTH_ERROR"
    system_error = "SYSTEM_ERROR"
    unknown_error = "UNKNOWN_ERROR"


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("idx_campaign_workspace_status", "workspace_id", "status"),
        Index("idx_campaign_workspace_created_by", "workspace_id", "created_by"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    status: CampaignStatus = Field(default=CampaignStatus.draft)
    created_by: uuid.UUID
    workspace_id: str = Field(sa_type=String(64), index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class CampaignContactImport(SQLModel, table=True):
    __tablename__ = "campaign_contact_imports"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    source_file_name: str = Field(max_length=255)
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    mapping_json: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    headers_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class CampaignContactStage(SQLModel, table=True):
    __tablename__ = "campaign_contact_staging"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    import_id: uuid.UUID = Field(foreign_key="campaign_contact_imports.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    row_number: int
    is_valid: bool = False
    mapped_data_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class CampaignSegment(SQLModel, table=True):
    __tablename__ = "campaign_segments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(max_length=255)
    estimated_count: int = 0
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class CampaignSegmentRule(SQLModel, table=True):
    __tablename__ = "campaign_segment_rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    segment_id: uuid.UUID = Field(foreign_key="campaign_segments.id", index=True)
    field_name: str = Field(max_length=100)
    operator: SegmentOperator
    value: str = Field(sa_type=Text)
    expression_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class CampaignChannelStrategy(SQLModel, table=True):
    __tablename__ = "campaign_channel_strategy"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    offer_pack_id: uuid.UUID | None = Field(default=None, foreign_key="offer_packs.id")
    offer_pack_version_id: uuid.UUID | None = Field(default=None, foreign_key="offer_pack_versions.id")
    strategy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class Template(SQLModel, table=True):
    __tablename__ = "templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(max_length=255)
    channel: str = Field(max_length=32)
    created_by: uuid.UUID
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TemplateVersion(SQLModel, table=True):
    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_template_version_number"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(foreign_key="templates.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    version_number: int
    status: TemplateStatus = Field(default=TemplateStatus.draft)
    subject: str | None = Field(default=None, max_length=255)
    content: str = Field(sa_type=Text)
    guardrail_compliant: bool = False
    guardrail_report_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TemplateToken(SQLModel, table=True):
    __tablename__ = "template_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(foreign_key="templates.id", index=True)
    name: str = Field(max_length=100)
    source_field: str = Field(max_length=100)
    default_value: str | None = Field(default=None, max_length=255)
    fallback_behavior: str = Field(default="defaultValue", max_length=50)


class OfferPack(SQLModel, table=True):
    __tablename__ = "offer_packs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    name: str = Field(max_length=255)
    created_by: uuid.UUID
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class OfferPackVersion(SQLModel, table=True):
    __tablename__ = "offer_pack_versions"
    __table_args__ = (
        UniqueConstraint("offer_pack_id", "version_number", name="uq_offer_pack_version_number"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_pack_id: uuid.UUID = Field(foreign_key="offer_packs.id", index=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    version_number: int
    status: TemplateStatus = Field(default=TemplateStatus.draft)
    is_default: bool = False
    guardrail_compliant: bool = False
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class OfferPackTemplateBinding(SQLModel, table=True):
    __tablename__ = "offer_pack_template_bindings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_pack_version_id: uuid.UUID = Field(foreign_key="offer_pack_versions.id", index=True)
    template_version_id: uuid.UUID = Field(foreign_key="template_versions.id", index=True)
    channel: str = Field(max_length=32)
    script_variant: str | None = Field(default=None, max_length=255)


class GovernancePolicy(SQLModel, table=True):
    __tablename__ = "governance_policies"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    campaign_id: uuid.UUID | None = Field(default=None, foreign_key="campaigns.id", index=True)
    scope: str = Field(max_length=32)
    policy_type: PolicyType
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: PolicyStatus = Field(default=PolicyStatus.active)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class CampaignPolicyBinding(SQLModel, table=True):
    __tablename__ = "campaign_policy_bindings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    policy_id: uuid.UUID = Field(foreign_key="governance_policies.id", index=True)


class GlobalControlState(SQLModel, table=True):
    __tablename__ = "global_control_state"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    campaign_id: uuid.UUID | None = Field(default=None, foreign_key="campaigns.id", index=True)
    paused: bool = False
    paused_by: uuid.UUID | None = None
    paused_reason: str | None = Field(default=None, max_length=255)
    paused_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Epic 2 — Contact delivery pipeline foundation
# ---------------------------------------------------------------------------


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    email: str = Field(sa_type=String(255), index=True)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str = Field(default="UTC", max_length=64)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ContactProgression(SQLModel, table=True):
    """Tracks the current delivery-pipeline state for one contact within a campaign."""

    __tablename__ = "contact_progression"
    __table_args__ = (
        UniqueConstraint(
            "contact_id", "campaign_id",
            name="uq_contact_progression_contact_campaign",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id", index=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    current_state: ContactProgressionState
    last_action_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ContactStateHistory(SQLModel, table=True):
    """Immutable audit trail of every state transition for a contact."""

    __tablename__ = "contact_state_history"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id", index=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    from_state: ContactProgressionState
    to_state: ContactProgressionState
    reason: str | None = Field(default=None, max_length=255)
    triggered_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class OutboxEvent(SQLModel, table=True):
    """Transactional outbox for reliable at-least-once event publishing."""

    __tablename__ = "outbox_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    aggregate_id: uuid.UUID = Field(index=True)
    aggregate_type: str = Field(max_length=64)  # "contact" | "campaign"
    event_type: str = Field(max_length=128)  # "contact.progressed" | "action.queued"
    event_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    idempotency_key: str = Field(unique=True, max_length=255, index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class ActionQueue(SQLModel, table=True):
    """Work item for the delivery worker — one outbound action per row."""

    __tablename__ = "action_queue"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    contact_id: uuid.UUID = Field(foreign_key="contacts.id", index=True)
    campaign_id: uuid.UUID = Field(foreign_key="campaigns.id", index=True)
    action_type: str = Field(max_length=64)  # "send_email" | "make_call" | "send_sms"
    channel: str = Field(max_length=32)      # "email" | "phone" | "sms"
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending", max_length=32, index=True)
    retry_count: int = Field(default=0)
    next_retry_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    executed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class ProviderCredential(SQLModel, table=True):
    """Per-workspace provider API credentials (stored encrypted at rest)."""

    __tablename__ = "provider_credentials"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    provider: NotificationProvider
    channel: str = Field(max_length=32)   # "email" | "sms" | "voice" | "scheduling"
    encrypted_api_key: str = Field(sa_type=Text)
    encrypted_api_secret: str | None = Field(default=None, sa_type=Text)
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ProviderEventLog(SQLModel, table=True):
    """Normalised inbound webhook events from external notification providers."""

    __tablename__ = "provider_event_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    provider: NotificationProvider
    provider_event_id: str = Field(max_length=255, index=True)
    event_type: str = Field(max_length=128)   # "bounce" | "delivered" | "opened"
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    normalized_event: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    received_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ImportRowError(SQLModel):
    row_number: int
    column: str
    semantic_error: SemanticError
    message: str


class PreviewRow(SQLModel):
    row_number: int
    data: dict[str, Any]


class HealthStatus(SQLModel):
    api: bool
    postgres: bool
    redis: bool


class CampaignCreate(SQLModel):
    name: str


class CampaignPublic(SQLModel):
    id: uuid.UUID
    name: str
    status: CampaignStatus
    workspace_id: str
    created_at: datetime


class CampaignsPublic(SQLModel):
    data: list[CampaignPublic]
    count: int


class CampaignImportPublic(SQLModel):
    import_id: uuid.UUID
    total_rows: int
    valid_rows: int
    invalid_rows: int
    requires_mapping: bool
    headers: list[str]
    errors: list[ImportRowError]


class CampaignMappingRequest(SQLModel):
    mapping: dict[str, str]


class ImportPreviewPublic(SQLModel):
    import_id: uuid.UUID
    preview_rows: list[PreviewRow]
    errors: list[ImportRowError]


class SegmentRuleInput(SQLModel):
    field_name: str
    operator: SegmentOperator
    value: str


class CampaignSegmentCreate(SQLModel):
    name: str
    rules: list[SegmentRuleInput]


class CampaignSegmentPublic(SQLModel):
    id: uuid.UUID
    name: str
    estimated_count: int


class StrategyRequest(SQLModel):
    offer_pack_id: uuid.UUID | None = None
    offer_pack_version_id: uuid.UUID | None = None
    channel_strategy: dict[str, Any] = Field(default_factory=dict)


class StrategyPublic(SQLModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    strategy_json: dict[str, Any]


class TokenDefinition(SQLModel):
    name: str
    source_field: str
    default_value: str | None = None
    fallback_behavior: str = "defaultValue"


class TemplateCreate(SQLModel):
    name: str
    channel: str
    subject: str | None = None
    content: str
    tokens: list[TokenDefinition] = Field(default_factory=list)


class TemplateUpdate(SQLModel):
    name: str | None = None
    subject: str | None = None
    content: str | None = None
    tokens: list[TokenDefinition] | None = None


class GuardrailViolation(SQLModel):
    semantic_error: SemanticError
    reason_code: str
    message: str


class TemplateVersionPublic(SQLModel):
    id: uuid.UUID
    version_number: int
    status: TemplateStatus
    guardrail_compliant: bool
    content: str
    subject: str | None = None


class TemplatePublic(SQLModel):
    id: uuid.UUID
    name: str
    channel: str
    workspace_id: str
    current_version: TemplateVersionPublic | None = None


class TemplatesPublic(SQLModel):
    data: list[TemplatePublic]
    count: int


class TemplatePreviewRequest(SQLModel):
    sample_payload: dict[str, Any] = Field(default_factory=dict)


class TemplatePreviewPublic(SQLModel):
    rendered_content: str
    unresolved_tokens: list[str]


class OfferPackBindingInput(SQLModel):
    template_version_id: uuid.UUID
    channel: str
    script_variant: str | None = None


class OfferPackCreate(SQLModel):
    name: str
    bindings: list[OfferPackBindingInput] = Field(default_factory=list)
    is_default: bool = False


class OfferPackVersionCreate(SQLModel):
    bindings: list[OfferPackBindingInput] = Field(default_factory=list)
    is_default: bool = False


class OfferPackVersionPublic(SQLModel):
    id: uuid.UUID
    version_number: int
    status: TemplateStatus
    is_default: bool
    guardrail_compliant: bool


class OfferPackPublic(SQLModel):
    id: uuid.UUID
    name: str
    workspace_id: str
    current_version: OfferPackVersionPublic | None = None


class OfferPacksPublic(SQLModel):
    data: list[OfferPackPublic]
    count: int


class GovernancePolicyCreate(SQLModel):
    scope: str
    policy_type: PolicyType
    campaign_id: uuid.UUID | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyPublic(SQLModel):
    id: uuid.UUID
    scope: str
    policy_type: PolicyType
    status: PolicyStatus
    payload_json: dict[str, Any]


class GovernancePoliciesPublic(SQLModel):
    data: list[GovernancePolicyPublic]
    count: int


class PolicyDecision(SQLModel):
    allowed: bool
    semantic_error: SemanticError | None = None
    reason_code: str | None = None
    next_eligible_at: datetime | None = None


class PolicyEvaluationRequest(SQLModel):
    campaign_id: uuid.UUID | None = None
    contact: dict[str, Any] = Field(default_factory=dict)
    campaign_daily_count: int = 0
    system_daily_count: int = 0
    requested_at: datetime | None = None


class PauseRequest(SQLModel):
    paused_reason: str


class ControlStatePublic(SQLModel):
    id: uuid.UUID
    paused: bool
    paused_reason: str | None = None
    paused_at: datetime | None = None
    action: str
    actor_id: uuid.UUID | None = None
    actor_role: str
    action_at: datetime



