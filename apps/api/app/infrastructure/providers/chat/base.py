"""Shared interface for inbound chatbot channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.chatbot.models import ChatbotChannelType


@dataclass(frozen=True)
class InboundChatMessage:
    """Normalized inbound message from a provider webhook."""

    channel_type: ChatbotChannelType
    provider_message_id: str
    visitor_id: str
    text: str | None
    is_text: bool
    is_opt_out: bool
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatDeliveryReceipt:
    """Provider send result."""

    accepted: bool
    provider_message_id: str | None = None
    status: str = "accepted"
    detail: str | None = None


class ChatChannelAdapter(ABC):
    """Common adapter contract for chat channel providers."""

    channel_type: ChatbotChannelType

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        """Verify a provider webhook request."""

    @abstractmethod
    def verify_challenge(self, query_params: dict[str, str], verify_token: str) -> str | None:
        """Return a provider challenge response when valid."""

    @abstractmethod
    def parse_event(self, payload: dict[str, Any]) -> list[InboundChatMessage]:
        """Parse provider payload into normalized inbound messages."""

    @abstractmethod
    async def send_message(
        self,
        visitor_id: str,
        text: str,
        *,
        customer_last_message_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ChatDeliveryReceipt:
        """Send a text message through the provider."""

    def normalize_visitor_id(self, raw_id: str) -> str:
        """Normalize a channel-specific visitor id."""
        return raw_id.strip()

    def is_opt_out(self, text: str | None) -> bool:
        """Detect opt-out commands."""
        return (text or "").strip().lower() in {
            "cancel",
            "opt out",
            "opt-out",
            "quit",
            "stop",
            "unsubscribe",
        }

    def is_non_text(self, message: dict[str, Any]) -> bool:
        """Detect non-text provider messages."""
        return "text" not in message
