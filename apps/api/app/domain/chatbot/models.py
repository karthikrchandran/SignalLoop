"""SQLModel persistence models for ChatBot Hub."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import UserDefinedType
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class PgVector(UserDefinedType):
    """Minimal pgvector column type without adding a Python package dependency."""

    cache_ok = True

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: Any) -> str:
        return f"vector({self.dimensions})"


class ChatbotChannelType(str, Enum):
    """Supported ChatBot Hub channel identifiers."""

    facebook_messenger = "facebook_messenger"
    whatsapp_business = "whatsapp_business"
    telegram = "telegram"
    linkedin_redirect = "linkedin_redirect"


class ChatbotChannelStatus(str, Enum):
    """Connection lifecycle for a chatbot channel."""

    draft = "draft"
    pending_approval = "pending_approval"
    connected = "connected"
    error = "error"
    disabled = "disabled"


class ChatbotKnowledgeSourceType(str, Enum):
    """Supported knowledge source types."""

    website = "website"
    document = "document"
    faq = "faq"
    manual_text = "manual_text"
    qa_pair = "qa_pair"


class ChatbotKnowledgeStatus(str, Enum):
    """Indexing lifecycle for a knowledge source."""

    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    failed = "failed"
    stale = "stale"
    archived = "archived"


class ChatbotConversationStatus(str, Enum):
    """Conversation lifecycle visible in the unified inbox."""

    open = "open"
    escalated = "escalated"
    agent_active = "agent_active"
    resolved = "resolved"
    bot_paused = "bot_paused"


class ChatbotLeadCaptureState(str, Enum):
    """Lead capture state for one visitor conversation."""

    none = "none"
    greeting = "greeting"
    open_conversation = "open_conversation"
    privacy_notice_prompt = "privacy_notice_prompt"
    collecting = "collecting"
    declined = "declined"
    lead_created = "lead_created"
    confirmed = "confirmed"


class ChatbotConversationOutcome(str, Enum):
    """Terminal or notable chatbot conversation outcome."""

    bot_resolved = "bot_resolved"
    escalated = "escalated"
    lead_captured = "lead_captured"


class ChatbotMessageDirection(str, Enum):
    """Message direction relative to EngageHub."""

    inbound = "inbound"
    outbound = "outbound"


class ChatbotMessageSender(str, Enum):
    """Actor that produced a conversation message."""

    visitor = "visitor"
    bot = "bot"
    agent = "agent"
    system = "system"


class ChatbotChannelConfig(SQLModel, table=True):
    """Per-workspace channel connection settings."""

    __tablename__ = "chatbot_channel_configs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel_type", name="uq_chatbot_channel_workspace_type"),
        Index("idx_chatbot_channel_workspace_status", "workspace_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    channel_type: ChatbotChannelType = Field(sa_type=String(32), index=True)
    display_name: str = Field(max_length=120)
    credential_id: uuid.UUID | None = Field(default=None, foreign_key="provider_credentials.id")
    status: ChatbotChannelStatus = Field(default=ChatbotChannelStatus.draft, sa_type=String(32))
    is_active: bool = Field(default=False)
    webhook_secret_hash: str | None = Field(default=None, sa_type=Text)
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    last_verified_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ChatbotBotConfig(SQLModel, table=True):
    """Shared bot behavior and compliance settings for a workspace."""

    __tablename__ = "chatbot_bot_configs"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_chatbot_bot_config_workspace"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    bot_name: str = Field(default="EngageHub Assistant", max_length=120)
    persona: str | None = Field(default=None, sa_type=Text)
    greeting_message: str | None = Field(default=None, sa_type=Text)
    escalation_message: str | None = Field(default=None, sa_type=Text)
    out_of_hours_message: str | None = Field(default=None, sa_type=Text)
    ai_disclosure: str = Field(default="AI assistant", max_length=255)
    token_cap_per_session: int = Field(default=4000)
    retention_days: int = Field(default=90)
    business_hours_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    lead_capture_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ChatbotKnowledgeSource(SQLModel, table=True):
    """Workspace-owned content source that can be indexed into the bot brain."""

    __tablename__ = "chatbot_knowledge_sources"
    __table_args__ = (
        Index("idx_chatbot_knowledge_workspace_status", "workspace_id", "status"),
        Index("idx_chatbot_knowledge_workspace_version", "workspace_id", "index_version"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    source_type: ChatbotKnowledgeSourceType = Field(sa_type=String(32), index=True)
    title: str = Field(max_length=255)
    source_uri: str | None = Field(default=None, sa_type=Text)
    status: ChatbotKnowledgeStatus = Field(default=ChatbotKnowledgeStatus.pending, sa_type=String(32))
    index_version: int = Field(default=1, index=True)
    content_hash: str | None = Field(default=None, max_length=128)
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    indexed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class ChatbotKnowledgeChunk(SQLModel, table=True):
    """Indexed chunk for retrieval-augmented chatbot answers."""

    __tablename__ = "chatbot_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_chatbot_chunk_source_index"),
        Index("idx_chatbot_chunk_workspace_version", "workspace_id", "index_version"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    source_id: uuid.UUID = Field(foreign_key="chatbot_knowledge_sources.id", index=True)
    index_version: int = Field(default=1, index=True)
    chunk_index: int
    content: str = Field(sa_type=Text)
    token_count: int = Field(default=0)
    embedding: list[float] | None = Field(default=None, sa_column=Column(PgVector(768), nullable=True))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ChatbotConversation(SQLModel, table=True):
    """Normalized thread shared by bot runtime, analytics, and human inbox."""

    __tablename__ = "chatbot_conversations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "channel_type",
            "visitor_id",
            name="uq_chatbot_conversation_workspace_visitor",
        ),
        Index("idx_chatbot_conversation_workspace_status", "workspace_id", "status"),
        Index("idx_chatbot_conversation_workspace_last_message", "workspace_id", "last_message_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    channel_type: ChatbotChannelType = Field(sa_type=String(32), index=True)
    visitor_id: str = Field(max_length=255, index=True)
    provider_thread_id: str | None = Field(default=None, max_length=255)
    contact_id: uuid.UUID | None = Field(default=None, foreign_key="contacts.id", index=True)
    status: ChatbotConversationStatus = Field(default=ChatbotConversationStatus.open, sa_type=String(32))
    index_version: int = Field(default=1)
    bot_paused: bool = Field(default=False)
    escalated: bool = Field(default=False)
    escalation_reason: str | None = Field(default=None, max_length=255)
    lead_capture_state: ChatbotLeadCaptureState = Field(
        default=ChatbotLeadCaptureState.none,
        sa_type=String(32),
    )
    lead_capture_intent: str | None = Field(default=None, max_length=128)
    outcome: ChatbotConversationOutcome | None = Field(default=None, sa_type=String(32))
    turn_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    consecutive_low_confidence_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    session_token_total: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    last_message_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), index=True)
    customer_last_message_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    resolved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ChatbotMessage(SQLModel, table=True):
    """One normalized inbound, outbound, or system message in a conversation."""

    __tablename__ = "chatbot_messages"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider_message_id",
            name="uq_chatbot_message_workspace_provider_message",
        ),
        Index("idx_chatbot_message_conversation_created", "conversation_id", "created_at"),
        Index("idx_chatbot_message_workspace_sender", "workspace_id", "sender"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    conversation_id: uuid.UUID = Field(foreign_key="chatbot_conversations.id", index=True)
    provider_message_id: str | None = Field(default=None, max_length=255)
    direction: ChatbotMessageDirection = Field(sa_type=String(16), index=True)
    sender: ChatbotMessageSender = Field(sa_type=String(16), index=True)
    message_type: str = Field(default="text", max_length=32)
    content: str | None = Field(default=None, sa_type=Text)
    bot_confidence: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    prompt_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    completion_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True), index=True)
    delivered_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), index=True)


class ChatbotOptOut(SQLModel, table=True):
    """Visitor-level opt-out state across chatbot channels."""

    __tablename__ = "chatbot_opt_outs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel_type", "visitor_id", name="uq_chatbot_opt_out_visitor"),
        Index("idx_chatbot_opt_out_workspace_created", "workspace_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    channel_type: ChatbotChannelType = Field(sa_type=String(32), index=True)
    visitor_id: str = Field(max_length=255, index=True)
    contact_id: uuid.UUID | None = Field(default=None, foreign_key="contacts.id", index=True)
    reason: str | None = Field(default=None, max_length=255)
    source_message_id: uuid.UUID | None = Field(default=None, foreign_key="chatbot_messages.id")
    reopt_in_invited_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class ChatbotAnalyticsSnapshot(SQLModel, table=True):
    """Aggregated chatbot metrics by workspace, date, and channel."""

    __tablename__ = "chatbot_analytics_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "snapshot_date",
            "channel_type",
            name="uq_chatbot_analytics_workspace_date_channel",
        ),
        Index("idx_chatbot_analytics_workspace_date", "workspace_id", "snapshot_date"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: str = Field(sa_type=String(64), index=True)
    snapshot_date: date = Field(sa_type=Date)
    channel_type: ChatbotChannelType | None = Field(default=None, sa_type=String(32))
    total_conversations: int = Field(default=0)
    bot_messages: int = Field(default=0)
    escalations: int = Field(default=0)
    leads_captured: int = Field(default=0)
    metrics_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
