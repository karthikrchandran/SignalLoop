"""Telegram Bot API chat adapter."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from app.domain.chatbot.models import ChatbotChannelType
from app.infrastructure.providers.chat.base import (
    ChatChannelAdapter,
    ChatDeliveryReceipt,
    InboundChatMessage,
)


class TelegramBotAdapter(ChatChannelAdapter):
    """Adapter for Telegram Bot API webhooks."""

    channel_type = ChatbotChannelType.telegram

    def verify_webhook(self, _body: bytes, headers: dict[str, str], secret: str) -> bool:
        return secrets.compare_digest(headers.get("x-telegram-bot-api-secret-token", ""), secret)

    def verify_challenge(self, _query_params: dict[str, str], _verify_token: str) -> str | None:
        return None

    def parse_event(self, payload: dict[str, Any]) -> list[InboundChatMessage]:
        message = payload.get("message") or payload.get("edited_message") or {}
        chat = message.get("chat") or {}
        visitor_id = self.normalize_visitor_id(str(chat.get("id") or ""))
        provider_message_id = str(message.get("message_id") or payload.get("update_id") or "")
        text = message.get("text") if isinstance(message.get("text"), str) else None
        if not visitor_id or not provider_message_id:
            return []
        return [
            InboundChatMessage(
                channel_type=self.channel_type,
                provider_message_id=provider_message_id,
                visitor_id=visitor_id,
                text=text,
                is_text=text is not None,
                is_opt_out=self.is_opt_out(text),
                raw_payload=message,
            )
        ]

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
