"""WhatsApp Cloud API chat adapter."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.chatbot.models import ChatbotChannelType
from app.infrastructure.providers.chat.base import (
    ChatChannelAdapter,
    ChatDeliveryReceipt,
    InboundChatMessage,
)


class WhatsAppWindowExpiredError(ValueError):
    """Raised when an outbound WhatsApp message violates the 24-hour window."""


class WhatsAppCloudAdapter(ChatChannelAdapter):
    """Adapter for Meta WhatsApp Cloud API webhooks."""

    channel_type = ChatbotChannelType.whatsapp_business

    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        signature = headers.get("x-hub-signature-256", "")
        if not signature.startswith("sha256="):
            return False
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, f"sha256={digest}")

    def verify_challenge(self, query_params: dict[str, str], verify_token: str) -> str | None:
        if query_params.get("hub.mode") == "subscribe" and query_params.get("hub.verify_token") == verify_token:
            return query_params.get("hub.challenge")
        return None

    def normalize_visitor_id(self, raw_id: str) -> str:
        return raw_id.strip().replace("+", "")

    def parse_event(self, payload: dict[str, Any]) -> list[InboundChatMessage]:
        messages: list[InboundChatMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                for message in value.get("messages", []):
                    provider_message_id = str(message.get("id") or "")
                    visitor_id = self.normalize_visitor_id(str(message.get("from") or ""))
                    text_body = (message.get("text") or {}).get("body")
                    text = text_body if isinstance(text_body, str) else None
                    if not provider_message_id or not visitor_id:
                        continue
                    messages.append(
                        InboundChatMessage(
                            channel_type=self.channel_type,
                            provider_message_id=provider_message_id,
                            visitor_id=visitor_id,
                            text=text,
                            is_text=text is not None,
                            is_opt_out=self.is_opt_out(text),
                            raw_payload=message,
                        )
                    )
        return messages

    async def send_message(
        self,
        visitor_id: str,
        text: str,
        *,
        customer_last_message_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ChatDeliveryReceipt:
        current = now or datetime.now(timezone.utc)
        if customer_last_message_at is None:
            raise WhatsAppWindowExpiredError("whatsapp_window_expired")
        last_message = customer_last_message_at
        if last_message.tzinfo is None:
            last_message = last_message.replace(tzinfo=timezone.utc)
        if current - last_message.astimezone(timezone.utc) > timedelta(hours=24):
            raise WhatsAppWindowExpiredError("whatsapp_window_expired")
        return ChatDeliveryReceipt(accepted=bool(visitor_id and text), status="queued")
