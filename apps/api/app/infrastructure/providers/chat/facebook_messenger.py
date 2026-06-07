"""Facebook Messenger chat adapter."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Any

from app.domain.chatbot.models import ChatbotChannelType
from app.infrastructure.providers.chat.base import (
    ChatChannelAdapter,
    ChatDeliveryReceipt,
    InboundChatMessage,
)


class FacebookMessengerAdapter(ChatChannelAdapter):
    """Adapter for Meta Facebook Page Messenger webhooks."""

    channel_type = ChatbotChannelType.facebook_messenger

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

    def parse_event(self, payload: dict[str, Any]) -> list[InboundChatMessage]:
        messages: list[InboundChatMessage] = []
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = str((event.get("sender") or {}).get("id") or "")
                message = event.get("message") or {}
                provider_message_id = str(message.get("mid") or event.get("timestamp") or "")
                text = message.get("text") if isinstance(message.get("text"), str) else None
                if not sender_id or not provider_message_id:
                    continue
                messages.append(
                    InboundChatMessage(
                        channel_type=self.channel_type,
                        provider_message_id=provider_message_id,
                        visitor_id=self.normalize_visitor_id(sender_id),
                        text=text,
                        is_text=text is not None,
                        is_opt_out=self.is_opt_out(text),
                        raw_payload=event,
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
        _ = (customer_last_message_at, now)
        return ChatDeliveryReceipt(accepted=bool(visitor_id and text), status="queued")
