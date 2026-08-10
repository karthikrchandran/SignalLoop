from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import chat_worker


def test_workspace_queue_rejects_payload_owned_by_another_workspace() -> None:
    redis = MagicMock()
    redis.brpop = AsyncMock(
        return_value=(
            "queue",
            {
                "workspace_id": "workspace-b",
                "channel_type": "whatsapp_business",
                "provider_message_id": "same-provider-id",
                "payload": {"visitor_id": "visitor-1"},
            },
        )
    )

    with (
        patch.object(chat_worker, "process_queue_item", new_callable=AsyncMock) as process,
        patch.object(chat_worker, "write_dead_letter", new_callable=AsyncMock) as dead_letter,
    ):
        processed = asyncio.run(
            chat_worker.consume_once(
                redis=redis,
                workspace_id="workspace-a",
                session_factory=MagicMock(),
                timeout_seconds=0,
            )
        )

    assert processed is False
    process.assert_not_awaited()
    dead_letter.assert_awaited_once()
