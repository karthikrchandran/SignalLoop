"""Redis-backed inbound queue, deduplication, and dead-letter helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.domain.chatbot.models import ChatbotChannelType

INBOUND_QUEUE_PREFIX = "chatbot:inbound"
DEDUP_PREFIX = "chatbot:dedup"
DEADLETTER_PREFIX = "chatbot:deadletter"
DEDUP_TTL_SECONDS = 60 * 60 * 24
DEADLETTER_TTL_SECONDS = 60 * 60 * 24 * 7


def inbound_queue_key(workspace_id: str) -> str:
    """Return the Redis queue key for inbound chatbot messages."""
    return f"{INBOUND_QUEUE_PREFIX}:{workspace_id}"


def dedup_key(workspace_id: str, channel_type: ChatbotChannelType, provider_message_id: str) -> str:
    """Return the Redis dedup key for one provider message."""
    return f"{DEDUP_PREFIX}:{workspace_id}:{channel_type.value}:{provider_message_id}"


def deadletter_key(workspace_id: str) -> str:
    """Return the Redis dead-letter key for a workspace."""
    return f"{DEADLETTER_PREFIX}:{workspace_id}"


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def enqueue_inbound_message(
    redis: Any,
    *,
    workspace_id: str,
    channel_type: ChatbotChannelType,
    provider_message_id: str,
    payload: dict[str, Any],
) -> str:
    """Deduplicate and enqueue an inbound message.

    Returns ``queued`` or ``duplicate``.
    """
    key = dedup_key(workspace_id, channel_type, provider_message_id)
    inserted = await redis.set(key, "1", ex=DEDUP_TTL_SECONDS, nx=True)
    if not inserted:
        return "duplicate"

    await redis.rpush(
        inbound_queue_key(workspace_id),
        json.dumps(
            {
                "workspace_id": workspace_id,
                "channel_type": channel_type.value,
                "provider_message_id": provider_message_id,
                "payload": payload,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            },
            default=_json_default,
        ),
    )
    return "queued"


async def write_dead_letter(
    redis: Any,
    *,
    workspace_id: str,
    channel_type: ChatbotChannelType,
    provider_message_id: str,
    payload: dict[str, Any],
    attempt_count: int,
    last_error: str,
) -> dict[str, Any]:
    """Write a visible dead-letter record for operator recovery."""
    record = {
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "channel_type": channel_type.value,
        "provider_message_id": provider_message_id,
        "payload": payload,
        "attempt_count": attempt_count,
        "last_error": last_error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "status": "dead_lettered",
    }
    key = deadletter_key(workspace_id)
    await redis.lpush(key, json.dumps(record, default=_json_default))
    await redis.expire(key, DEADLETTER_TTL_SECONDS)
    return record


async def list_dead_letters(redis: Any, workspace_id: str) -> list[dict[str, Any]]:
    """Return visible dead-letter records for one workspace."""
    rows = await redis.lrange(deadletter_key(workspace_id), 0, -1)
    return [json.loads(row) for row in rows]


async def retry_dead_letter(redis: Any, workspace_id: str, dead_letter_id: str) -> tuple[dict[str, Any], str]:
    """Move a dead-letter record back to the inbound queue."""
    key = deadletter_key(workspace_id)
    rows = await redis.lrange(key, 0, -1)
    for row in rows:
        record = json.loads(row)
        if record.get("id") != dead_letter_id:
            continue

        original_payload = record.get("payload")
        if isinstance(original_payload, dict) and isinstance(original_payload.get("payload"), dict):
            retry_payload = dict(original_payload)
        else:
            retry_payload = {
                "workspace_id": workspace_id,
                "channel_type": record.get("channel_type"),
                "provider_message_id": record.get("provider_message_id"),
                "payload": original_payload if isinstance(original_payload, dict) else {},
            }
        retry_payload["retried_at"] = datetime.now(timezone.utc).isoformat()
        retry_payload["retry_of_dead_letter_id"] = dead_letter_id
        queue_key = inbound_queue_key(workspace_id)
        await redis.rpush(queue_key, json.dumps(retry_payload, default=_json_default))
        await redis.lrem(key, 1, row)
        return record, queue_key

    raise KeyError(dead_letter_id)
