from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import Any

from sqlmodel import Session, SQLModel, create_engine

from app.domain.chatbot.models import (
    ChatbotChannelConfig,
    ChatbotChannelType,
)
from app.domain.chatbot.repositories import get_channel_config_by_id
from app.domain.chatbot.webhook_ingestion import (
    deadletter_key,
    enqueue_inbound_message,
    inbound_queue_key,
    list_dead_letters,
    retry_dead_letter,
    write_dead_letter,
)
from app.domain_models import NotificationProvider
from app.infrastructure.providers.chat.facebook_messenger import (
    FacebookMessengerAdapter,
)
from app.infrastructure.providers.chat.registry import (
    build_chat_adapter,
    provider_for_channel,
)
from app.infrastructure.providers.chat.telegram_bot import TelegramBotAdapter
from app.infrastructure.providers.chat.whatsapp_cloud import WhatsAppCloudAdapter


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.expires: dict[str, int] = {}

    async def set(self, key: str, value: str, *, ex: int, nx: bool) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.expires[key] = ex
        return True

    async def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        rows = self.lists.get(key, [])
        if end == -1:
            return rows[start:]
        return rows[start : end + 1]

    async def lrem(self, key: str, count: int, value: str) -> int:
        rows = self.lists.get(key, [])
        removed = 0
        next_rows = []
        for row in rows:
            if row == value and (count == 0 or removed < count):
                removed += 1
                continue
            next_rows.append(row)
        self.lists[key] = next_rows
        return removed

    async def expire(self, key: str, seconds: int) -> bool:
        self.expires[key] = seconds
        return True


def _signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_provider_registry_maps_supported_channels() -> None:
    assert provider_for_channel(ChatbotChannelType.facebook_messenger) == NotificationProvider.facebook_messenger
    assert provider_for_channel(ChatbotChannelType.whatsapp_business) == NotificationProvider.whatsapp_cloud
    assert provider_for_channel(ChatbotChannelType.telegram) == NotificationProvider.telegram_bot
    assert build_chat_adapter(ChatbotChannelType.facebook_messenger).channel_type == ChatbotChannelType.facebook_messenger


def test_facebook_adapter_verifies_signature_and_parses_text_and_non_text() -> None:
    adapter = FacebookMessengerAdapter()
    payload: dict[str, Any] = {
        "entry": [
            {
                "messaging": [
                    {"sender": {"id": "fb-user"}, "message": {"mid": "m1", "text": "STOP"}},
                    {"sender": {"id": "fb-user"}, "message": {"mid": "m2", "attachments": [{"type": "image"}]}},
                ]
            }
        ]
    }
    body = json.dumps(payload).encode()

    assert adapter.verify_webhook(body, {"x-hub-signature-256": _signature("secret", body)}, "secret")
    assert not adapter.verify_webhook(body, {"x-hub-signature-256": "sha256=bad"}, "secret")

    messages = adapter.parse_event(payload)

    assert messages[0].provider_message_id == "m1"
    assert messages[0].is_opt_out is True
    assert messages[1].is_text is False


def test_whatsapp_adapter_normalizes_phone_and_detects_non_text() -> None:
    adapter = WhatsAppCloudAdapter()
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"id": "wamid.1", "from": "+15551234567", "text": {"body": "hello"}},
                                {"id": "wamid.2", "from": "+15551234567", "image": {"id": "img"}},
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = adapter.parse_event(payload)

    assert messages[0].visitor_id == "15551234567"
    assert messages[0].is_text is True
    assert messages[1].is_text is False


def test_telegram_adapter_requires_exact_secret_token() -> None:
    adapter = TelegramBotAdapter()
    payload = {"update_id": 42, "message": {"message_id": 7, "chat": {"id": 123}, "text": "unsubscribe"}}

    assert adapter.verify_webhook(b"{}", {"x-telegram-bot-api-secret-token": "secret"}, "secret")
    assert not adapter.verify_webhook(b"{}", {"x-telegram-bot-api-secret-token": "wrong"}, "secret")
    message = adapter.parse_event(payload)[0]
    assert message.visitor_id == "123"
    assert message.is_opt_out is True


def test_enqueue_inbound_message_deduplicates_provider_message_id() -> None:
    async def scenario() -> None:
        redis = FakeRedis()
        payload = {"text": "hello"}

        first = await enqueue_inbound_message(
            redis,
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.facebook_messenger,
            provider_message_id="m1",
            payload=payload,
        )
        second = await enqueue_inbound_message(
            redis,
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.facebook_messenger,
            provider_message_id="m1",
            payload=payload,
        )

        assert first == "queued"
        assert second == "duplicate"
        assert len(redis.lists[inbound_queue_key("ws-a")]) == 1

    asyncio.run(scenario())


def test_dead_letter_retry_requeues_and_removes_visible_record() -> None:
    async def scenario() -> None:
        redis = FakeRedis()
        record = await write_dead_letter(
            redis,
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.whatsapp_business,
            provider_message_id="wamid.1",
            payload={
                "workspace_id": "ws-a",
                "channel_type": "whatsapp_business",
                "provider_message_id": "wamid.1",
                "payload": {"visitor_id": "15551234567", "text": "hello", "is_text": True},
            },
            attempt_count=3,
            last_error="timeout",
        )

        rows = await list_dead_letters(redis, "ws-a")
        retried, queue_key = await retry_dead_letter(redis, "ws-a", record["id"])

        assert rows[0]["provider_message_id"] == "wamid.1"
        assert retried["id"] == record["id"]
        assert queue_key == inbound_queue_key("ws-a")
        assert redis.lists[deadletter_key("ws-a")] == []
        assert len(redis.lists[inbound_queue_key("ws-a")]) == 1
        retry_row = json.loads(redis.lists[inbound_queue_key("ws-a")][0])
        assert retry_row["provider_message_id"] == "wamid.1"
        assert retry_row["payload"]["visitor_id"] == "15551234567"
        assert retry_row["retry_of_dead_letter_id"] == record["id"]

    asyncio.run(scenario())


def test_channel_lookup_is_workspace_scoped_by_id() -> None:
    with _session() as session:
        channel = ChatbotChannelConfig(
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.telegram,
            display_name="Telegram A",
        )
        session.add(channel)
        session.commit()
        session.refresh(channel)

        assert get_channel_config_by_id("ws-a", session, channel.id) is not None
        assert get_channel_config_by_id("ws-b", session, channel.id) is None
