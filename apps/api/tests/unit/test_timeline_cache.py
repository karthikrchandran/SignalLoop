"""Tests for timeline cache invalidation helpers."""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock


def _run(coro):
    return asyncio.run(coro)


def _make_request(redis_client) -> MagicMock:
    request = MagicMock()
    request.app.state.redis_manager.client = redis_client
    return request


def test_timeline_cache_keys_include_all_and_campaign_specific_keys() -> None:
    from app.domain.timeline.timeline_service import timeline_cache_keys

    contact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    campaign_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    assert timeline_cache_keys(contact_id, campaign_id) == (
        "timeline:11111111111111111111111111111111:all:page1",
        "timeline:11111111111111111111111111111111:22222222222222222222222222222222:page1",
    )


def test_invalidate_timeline_cache_for_client_deletes_all_cache_scopes() -> None:
    from app.domain.timeline.timeline_service import invalidate_timeline_cache_for_client

    contact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    campaign_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    redis = MagicMock()
    redis.delete = AsyncMock()

    _run(invalidate_timeline_cache_for_client(redis, contact_id, campaign_id))

    redis.delete.assert_awaited_once_with(
        "timeline:11111111111111111111111111111111:all:page1",
        "timeline:11111111111111111111111111111111:22222222222222222222222222222222:page1",
    )


def test_invalidate_timeline_cache_from_url_closes_transient_client(monkeypatch) -> None:
    from app.domain.timeline import timeline_service

    contact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    campaign_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    redis = MagicMock()
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()
    from_url = MagicMock(return_value=redis)
    monkeypatch.setattr("redis.asyncio.Redis.from_url", from_url)

    _run(
        timeline_service.invalidate_timeline_cache_from_url(
            "redis://example/0",
            contact_id,
            campaign_id,
        )
    )

    from_url.assert_called_once_with(
        "redis://example/0",
        encoding="utf-8",
        decode_responses=True,
    )
    redis.delete.assert_awaited_once_with(
        "timeline:11111111111111111111111111111111:all:page1",
        "timeline:11111111111111111111111111111111:22222222222222222222222222222222:page1",
    )
    redis.aclose.assert_awaited_once()


def test_invalidate_timeline_cache_from_url_sync_runs_async_helper(monkeypatch) -> None:
    from app.domain.timeline import timeline_service

    calls = []

    async def fake_invalidate(redis_url, contact_id, campaign_id=None):
        calls.append((redis_url, contact_id, campaign_id))

    monkeypatch.setattr(
        timeline_service,
        "invalidate_timeline_cache_from_url",
        fake_invalidate,
    )
    contact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    campaign_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

    timeline_service.invalidate_timeline_cache_from_url_sync(
        "redis://example/0",
        contact_id,
        campaign_id,
    )

    assert calls == [("redis://example/0", contact_id, campaign_id)]


def test_get_cached_returns_cached_page_payload() -> None:
    from app.domain.timeline import timeline_service

    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "data": [
                    {
                        "id": "ce_11111111111111111111111111111111",
                        "source_system": "contact_events",
                        "event_type": "email_sent",
                        "channel": "email",
                        "timestamp": "2026-05-06T14:30:00Z",
                        "actor": "system",
                        "outcome": "sent",
                        "reason_code": "high_intent",
                        "has_detail": True,
                    }
                ],
                "count": 250,
            }
        )
    )
    request = _make_request(redis)

    result = _run(timeline_service._get_cached(request, "timeline:key"))

    assert result is not None
    assert result["count"] == 250
    assert result["data"][0]["event_type"] == "email_sent"


def test_invalidate_timeline_cache_request_uses_app_redis_client() -> None:
    from app.domain.timeline.timeline_service import invalidate_timeline_cache

    contact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    campaign_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    redis = MagicMock()
    redis.delete = AsyncMock()
    request = _make_request(redis)

    _run(invalidate_timeline_cache(request, contact_id, campaign_id))

    redis.delete.assert_awaited_once_with(
        "timeline:11111111111111111111111111111111:all:page1",
        "timeline:11111111111111111111111111111111:22222222222222222222222222222222:page1",
    )


def test_invalidate_timeline_cache_swallows_missing_redis_manager() -> None:
    from app.domain.timeline.timeline_service import invalidate_timeline_cache

    contact_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    request = MagicMock()
    type(request.app.state).redis_manager = property(
        lambda self: (_ for _ in ()).throw(AttributeError("no redis_manager"))
    )

    _run(invalidate_timeline_cache(request, contact_id))