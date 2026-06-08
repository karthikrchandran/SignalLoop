"""API schemas for the ChatBot Hub foundation slice."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.chatbot.models import (
    ChatbotChannelStatus,
    ChatbotChannelType,
    ChatbotConversationOutcome,
    ChatbotConversationStatus,
    ChatbotKnowledgeSourceType,
    ChatbotKnowledgeStatus,
    ChatbotMessageDirection,
    ChatbotMessageSender,
)


class ChatbotHealthPublic(BaseModel):
    """Health response for authenticated ChatBot Hub routes."""

    status: str
    workspace_id: str
    feature: str = "chatbot_hub"


class ChatbotNavigationItem(BaseModel):
    """Navigation item exposed for clients that want role-aware route metadata."""

    key: str
    title: str
    path: str
    admin_only: bool = False


class ChatbotNavigationPublic(BaseModel):
    """Role-filtered chatbot navigation list."""

    data: list[ChatbotNavigationItem]
    count: int


class ChatbotCredentialInput(BaseModel):
    """Credential material for channel setup. Plaintext is never returned."""

    api_key: str = Field(min_length=1)
    api_secret: str | None = None
    webhook_secret: str | None = None


class ChatbotChannelCreate(BaseModel):
    """Create request for a chatbot channel config."""

    channel_type: ChatbotChannelType
    display_name: str = Field(min_length=1, max_length=120)
    credentials: ChatbotCredentialInput
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False


class ChatbotChannelUpdate(BaseModel):
    """Update request for a chatbot channel config."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    credentials: ChatbotCredentialInput | None = None
    config_json: dict[str, Any] | None = None
    is_active: bool | None = None


class ChatbotChannelToggle(BaseModel):
    """Toggle request for channel activation."""

    is_active: bool


class ChatbotChannelReadinessPublic(BaseModel):
    """Real-connect checklist for a configured chatbot channel."""

    ready: bool
    status: str
    missing: list[str] = Field(default_factory=list)
    webhook_url_path: str


class ChatbotChannelPublic(BaseModel):
    """Masked API response for a chatbot channel config."""

    id: UUID
    workspace_id: str
    channel_type: ChatbotChannelType
    display_name: str
    status: ChatbotChannelStatus
    is_active: bool
    has_credential: bool
    config_json: dict[str, Any]
    readiness: ChatbotChannelReadinessPublic
    last_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChatbotChannelsPublic(BaseModel):
    """List response for chatbot channel configs."""

    data: list[ChatbotChannelPublic]
    count: int


class ChatbotDeadLetterPublic(BaseModel):
    """Visible dead-letter record for operator recovery."""

    id: str
    workspace_id: str
    channel_type: ChatbotChannelType
    provider_message_id: str
    payload: dict[str, Any]
    attempt_count: int
    last_error: str
    failed_at: datetime
    status: str = "dead_lettered"


class ChatbotDeadLettersPublic(BaseModel):
    """List response for dead-lettered chatbot messages."""

    data: list[ChatbotDeadLetterPublic]
    count: int


class ChatbotDeadLetterRetryPublic(BaseModel):
    """Retry response for a dead-lettered chatbot message."""

    id: str
    requeued: bool
    inbound_queue_key: str


class ChatbotAnalyticsTotalsPublic(BaseModel):
    """Top-level chatbot analytics totals for one workspace and date range."""

    conversations: int
    containment_rate: float
    leads_captured: int
    escalations: int
    bot_messages: int
    opt_outs: int


class ChatbotAnalyticsSeriesPointPublic(BaseModel):
    """Daily chatbot analytics point."""

    date: date
    conversations: int
    bot_messages: int
    leads_captured: int
    escalations: int
    opt_outs: int


class ChatbotAnalyticsChannelBreakdownPublic(BaseModel):
    """Per-channel chatbot analytics row."""

    channel_type: ChatbotChannelType
    bot_resolved: int
    escalated: int
    lead_captured: int
    opted_out: int
    conversations: int


class ChatbotAnalyticsConversionFunnelPublic(BaseModel):
    """Lead conversion funnel from chatbot conversation into follow-up workflows."""

    conversations: int
    leads_captured: int
    prospecting_researched: int
    added_to_campaign: int
    sequence_enrolled: int
    voice_followups: int


class ChatbotAnalyticsPublic(BaseModel):
    """Chatbot analytics response for the current workspace."""

    workspace_id: str
    date_from: date
    date_to: date
    updated_at: datetime
    totals: ChatbotAnalyticsTotalsPublic
    conversion_funnel: ChatbotAnalyticsConversionFunnelPublic
    timeseries: list[ChatbotAnalyticsSeriesPointPublic]
    channel_breakdown: list[ChatbotAnalyticsChannelBreakdownPublic]


class ChatbotKnowledgeSourceCreate(BaseModel):
    """Create request for a knowledge source."""

    source_type: ChatbotKnowledgeSourceType
    title: str = Field(min_length=1, max_length=255)
    source_uri: str | None = None
    content: str | None = None
    question: str | None = None
    answer: str | None = None
    crawl_depth: int = Field(default=1, ge=1, le=5)
    max_pages: int = Field(default=10, ge=1, le=50)


class ChatbotKnowledgeSourceUpdate(BaseModel):
    """Update request for a knowledge source."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    source_uri: str | None = None
    content: str | None = None
    question: str | None = None
    answer: str | None = None
    crawl_depth: int | None = Field(default=None, ge=1, le=5)
    max_pages: int | None = Field(default=None, ge=1, le=50)


class ChatbotKnowledgeSourcePublic(BaseModel):
    """API response for a knowledge source."""

    id: UUID
    workspace_id: str
    source_type: ChatbotKnowledgeSourceType
    title: str
    source_uri: str | None = None
    status: ChatbotKnowledgeStatus
    index_version: int
    chunk_count: int = 0
    error_message: str | None = None
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None = None


class ChatbotKnowledgeSourcesPublic(BaseModel):
    """List response for knowledge sources."""

    data: list[ChatbotKnowledgeSourcePublic]
    count: int


class ChatbotKnowledgeStatusPublic(BaseModel):
    """Index status response for one source."""

    id: UUID
    workspace_id: str
    status: ChatbotKnowledgeStatus
    index_version: int
    chunk_count: int
    progress: int
    error_message: str | None = None
    indexed_at: datetime | None = None


class ChatbotReindexRequest(BaseModel):
    """Manual reindex request."""

    source_ids: list[UUID] | None = None


class ChatbotReindexPublic(BaseModel):
    """Manual reindex response."""

    job_id: str
    queued: int
    workspace_id: str
    status: str = "queued"


class ChatbotTestBotRequest(BaseModel):
    """Admin Test Bot request."""

    question: str = Field(min_length=1, max_length=1000)
    index_version: int | None = None


class ChatbotTestBotSource(BaseModel):
    """Source chunk used by Test Bot."""

    source_id: UUID
    source_title: str
    chunk_id: UUID
    excerpt: str
    score: float


class ChatbotTestBotResponse(BaseModel):
    """Grounded Test Bot response."""

    answer: str
    ai_disclosure: str
    sources: list[ChatbotTestBotSource]
    no_kb: bool = False


class ChatbotLeadDetails(BaseModel):
    """Captured lead details safe for inbox/export display."""

    contact_id: UUID | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    source_channel: str | None = None
    tags: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)


class ChatbotThreadSummary(BaseModel):
    """Inbox thread list item."""

    id: UUID
    workspace_id: str
    channel_type: ChatbotChannelType
    visitor_id: str
    status: ChatbotConversationStatus
    outcome: ChatbotConversationOutcome | None = None
    preview: str | None = None
    last_message_at: datetime | None = None
    customer_last_message_at: datetime | None = None
    is_whatsapp_window_open: bool = True
    is_opted_out: bool = False
    escalation_reason: str | None = None
    lead: ChatbotLeadDetails | None = None


class ChatbotThreadsPublic(BaseModel):
    """Paginated inbox thread list."""

    data: list[ChatbotThreadSummary]
    count: int
    next_cursor: str | None = None


class ChatbotThreadMessagePublic(BaseModel):
    """Message row returned in thread detail."""

    id: UUID
    direction: ChatbotMessageDirection
    sender: ChatbotMessageSender
    message_type: str
    content: str | None = None
    bot_confidence: float | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    delivered_at: datetime | None = None


class ChatbotThreadDetailPublic(ChatbotThreadSummary):
    """Inbox thread detail with ordered messages."""

    messages: list[ChatbotThreadMessagePublic]


class ChatbotThreadReplyRequest(BaseModel):
    """Agent reply request."""

    message: str = Field(min_length=1, max_length=4000)


class ChatbotThreadActionPublic(BaseModel):
    """Thread mutation response."""

    thread: ChatbotThreadDetailPublic


class ChatbotExportFormat(str):
    """Conversation export format values."""


class ChatbotBusinessHoursConfig(BaseModel):
    """Business hours config for the settings screen."""

    enabled: bool = False
    timezone: str = "UTC"
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    start: str = "09:00"
    end: str = "17:00"


class ChatbotLeadCaptureConfig(BaseModel):
    """Lead capture config for the settings screen."""

    enabled: bool = True
    min_turns: int = Field(default=3, ge=1, le=20)
    intent_keywords: list[str] = Field(default_factory=lambda: ["demo", "pricing", "buy"])
    privacy_notice_text: str | None = None
    privacy_policy_url: str | None = None
    re_opt_in_invitation_enabled: bool = False
    confidence_threshold: float = Field(default=0.25, ge=0, le=1)


class ChatbotConfigPublic(BaseModel):
    """Workspace bot config response."""

    workspace_id: str
    bot_name: str
    persona: str | None = None
    greeting_message: str | None = None
    escalation_message: str | None = None
    out_of_hours_message: str | None = None
    ai_disclosure: str
    token_cap_per_session: int
    retention_days: int
    business_hours: ChatbotBusinessHoursConfig
    lead_capture: ChatbotLeadCaptureConfig
    reindex_schedule_time: str = "02:00"
    channel_overrides: list[ChatbotChannelPublic] = Field(default_factory=list)
    updated_at: datetime


class ChatbotConfigUpdate(BaseModel):
    """Workspace bot config update request."""

    bot_name: str | None = Field(default=None, min_length=1, max_length=120)
    persona: str | None = None
    greeting_message: str | None = None
    escalation_message: str | None = None
    out_of_hours_message: str | None = None
    ai_disclosure: str | None = Field(default=None, min_length=10, max_length=255)
    token_cap_per_session: int | None = Field(default=None, ge=1, le=20000)
    retention_days: int | None = Field(default=None, ge=30)
    business_hours: ChatbotBusinessHoursConfig | None = None
    lead_capture: ChatbotLeadCaptureConfig | None = None
    reindex_schedule_time: str | None = None


class ChatbotOptOutPublic(BaseModel):
    """Admin-visible opt-out row."""

    id: UUID
    workspace_id: str
    channel_type: ChatbotChannelType
    visitor_id: str
    contact_id: UUID | None = None
    reason: str | None = None
    actor: str = "visitor"
    created_at: datetime
    reopt_in_invited_at: datetime | None = None


class ChatbotOptOutsPublic(BaseModel):
    """List response for opt-outs."""

    data: list[ChatbotOptOutPublic]
    count: int


class ChatbotOptOutDeletePublic(BaseModel):
    """Opt-out re-enable response."""

    id: UUID
    removed: bool


class ChatbotRetentionPurgePublic(BaseModel):
    """Retention purge job result."""

    workspace_id: str
    cutoff_at: datetime
    conversations_purged: int
    messages_purged: int
