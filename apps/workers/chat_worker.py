"""ChatBot Hub inbound message worker."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from typing import Any

from redis.asyncio import Redis
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.domain.chatbot.engine import BotRuntimeInput, ConversationEngine
from app.domain.chatbot.models import ChatbotChannelType
from app.domain.chatbot.retention import (
    RetentionPurgeResult,
    purge_workspace_conversations,
)
from app.domain.chatbot.webhook_ingestion import inbound_queue_key, write_dead_letter
from app.infrastructure.providers.chat.registry import build_chat_adapter

logger = logging.getLogger(__name__)
MAX_RETRIES = 3
RETENTION_INTERVAL_SECONDS = 24 * 60 * 60


def _decode_queue_row(raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        raw = raw.decode()
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("Queue row must be a JSON object")
    return loaded


def _runtime_input(row: dict[str, Any]) -> BotRuntimeInput:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    channel_value = row.get("channel_type") or payload.get("channel_type")
    provider_message_id = str(row.get("provider_message_id") or payload.get("provider_message_id") or "")
    visitor_id = str(payload.get("visitor_id") or row.get("visitor_id") or "")
    if not channel_value or not provider_message_id or not visitor_id:
        raise ValueError("Queue row is missing channel_type, provider_message_id, or visitor_id")
    return BotRuntimeInput(
        workspace_id=str(row.get("workspace_id") or payload.get("workspace_id") or ""),
        channel_type=ChatbotChannelType(str(channel_value)),
        visitor_id=visitor_id,
        provider_message_id=provider_message_id,
        text=payload.get("text") if isinstance(payload.get("text"), str) else None,
        is_text=bool(payload.get("is_text", payload.get("text") is not None)),
        is_opt_out=bool(payload.get("is_opt_out")),
        raw_payload=payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else payload,
    )


async def process_queue_item(
    *,
    redis: Any,
    session: Session,
    raw: str | bytes | dict[str, Any],
) -> None:
    """Process one queued inbound message and commit its DB effects."""
    row = _decode_queue_row(raw)
    inbound = _runtime_input(row)
    adapter = build_chat_adapter(inbound.channel_type)
    engine_instance = ConversationEngine(session=session, redis=redis, adapter=adapter)
    await engine_instance.process(inbound)
    session.commit()


async def consume_once(
    *,
    redis: Any,
    workspace_id: str,
    session_factory: Callable[[], Session] | None = None,
    timeout_seconds: int = 5,
) -> bool:
    """BRPOP one workspace queue item. Returns true when a message was processed."""
    key = inbound_queue_key(workspace_id)
    row = await redis.brpop(key, timeout=timeout_seconds)
    if not row:
        return False
    raw = row[1] if isinstance(row, tuple) else row
    factory = session_factory or (lambda: Session(engine))
    with factory() as session:
        payload_for_dead_letter = _decode_queue_row(raw)
        channel_type = ChatbotChannelType(payload_for_dead_letter.get("channel_type"))
        provider_message_id = str(payload_for_dead_letter.get("provider_message_id") or "")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await process_queue_item(redis=redis, session=session, raw=payload_for_dead_letter)
                return True
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                if attempt == MAX_RETRIES:
                    await write_dead_letter(
                        redis,
                        workspace_id=workspace_id,
                        channel_type=channel_type,
                        provider_message_id=provider_message_id,
                        payload=payload_for_dead_letter,
                        attempt_count=attempt,
                        last_error=str(exc),
                    )
                    logger.exception("Dead-lettered chatbot message after retries")
                    return False
                await asyncio.sleep(2**attempt)
    return False


async def run_worker(workspace_id: str, redis_url: str | None = None) -> None:
    """Run the ChatBot Hub worker for one workspace queue."""
    redis = Redis.from_url(redis_url or str(settings.REDIS_URL), encoding="utf-8", decode_responses=True)
    try:
        while True:
            await consume_once(redis=redis, workspace_id=workspace_id)
    finally:
        await redis.aclose()


def run_retention_purge_once(workspace_id: str) -> RetentionPurgeResult:
    """Run one retention purge pass for a workspace."""
    with Session(engine) as session:
        result = purge_workspace_conversations(session, workspace_id=workspace_id)
        session.commit()
        return result


async def run_retention_scheduler(
    workspace_id: str,
    *,
    interval_seconds: int = RETENTION_INTERVAL_SECONDS,
    initial_delay_seconds: int = 0,
) -> None:
    """Run retention purge repeatedly for a workspace."""
    if interval_seconds <= 0:
        raise ValueError("Retention interval must be greater than zero")
    if initial_delay_seconds > 0:
        await asyncio.sleep(initial_delay_seconds)

    while True:
        result = run_retention_purge_once(workspace_id)
        logger.info(
            "Chatbot retention purge completed",
            extra={
                "workspace_id": workspace_id,
                "conversations_purged": result.conversations_purged,
                "messages_purged": result.messages_purged,
            },
        )
        await asyncio.sleep(interval_seconds)


def main() -> None:
    """CLI entry point. Requires CHATBOT_WORKSPACE_ID to avoid scanning queues."""
    workspace_id = getattr(settings, "CHATBOT_WORKSPACE_ID", None)
    if not workspace_id:
        raise SystemExit("Set CHATBOT_WORKSPACE_ID to run chat_worker")
    mode = os.getenv("CHATBOT_WORKER_MODE", "inbound").strip().lower()
    if mode == "retention-once":
        result = run_retention_purge_once(str(workspace_id))
        logger.info(
            "Chatbot retention purge completed",
            extra={
                "workspace_id": str(workspace_id),
                "conversations_purged": result.conversations_purged,
                "messages_purged": result.messages_purged,
            },
        )
        return
    if mode == "retention":
        interval_seconds = int(os.getenv("CHATBOT_RETENTION_INTERVAL_SECONDS", str(RETENTION_INTERVAL_SECONDS)))
        asyncio.run(run_retention_scheduler(str(workspace_id), interval_seconds=interval_seconds))
        return
    if mode != "inbound":
        raise SystemExit("CHATBOT_WORKER_MODE must be inbound, retention, or retention-once")
    asyncio.run(run_worker(str(workspace_id)))


if __name__ == "__main__":
    main()
