"""Tests for ``app.core.idempotency`` Redis-backed dedup helpers."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock


def _run(coro):
    return asyncio.run(coro)


def _make_request(redis_client) -> MagicMock:
    """Build a minimal ``Request`` stub exposing ``app.state.redis_manager.client``."""
    request = MagicMock()
    request.app.state.redis_manager.client = redis_client
    return request


# ---------------------------------------------------------------------------
# check_idempotency
# ---------------------------------------------------------------------------


def test_check_idempotency_returns_none_when_redis_client_is_none() -> None:
    """If the Redis client isn't initialised, the helper short-circuits to None."""
    from app.core.idempotency import check_idempotency

    request = _make_request(None)
    assert _run(check_idempotency(request, "key-1")) is None


def test_check_idempotency_returns_parsed_json_when_cached() -> None:
    """A cached payload must be JSON-decoded and returned."""
    from app.core.idempotency import check_idempotency

    payload = {"status": "ok", "id": 42}
    redis = MagicMock()
    redis.get = AsyncMock(return_value=json.dumps(payload))
    request = _make_request(redis)

    result = _run(check_idempotency(request, "abc"))

    assert result == payload
    redis.get.assert_awaited_once_with("idempotency:abc")


def test_check_idempotency_returns_none_when_cache_miss() -> None:
    """Empty/missing cache value yields None."""
    from app.core.idempotency import check_idempotency

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    request = _make_request(redis)

    assert _run(check_idempotency(request, "missing")) is None


def test_check_idempotency_swallows_redis_errors() -> None:
    """Redis exceptions must never bubble up — return None instead."""
    from app.core.idempotency import check_idempotency

    redis = MagicMock()
    redis.get = AsyncMock(side_effect=RuntimeError("redis down"))
    request = _make_request(redis)

    assert _run(check_idempotency(request, "boom")) is None


def test_check_idempotency_swallows_attribute_errors() -> None:
    """A request without a redis_manager must also be tolerated."""
    from app.core.idempotency import check_idempotency

    request = MagicMock()
    type(request.app.state).redis_manager = property(
        lambda self: (_ for _ in ()).throw(AttributeError("no redis_manager"))
    )

    assert _run(check_idempotency(request, "k")) is None


# ---------------------------------------------------------------------------
# store_idempotent_response
# ---------------------------------------------------------------------------


def test_store_idempotent_response_noops_when_redis_client_is_none() -> None:
    """No Redis client -> nothing should happen, no exception raised."""
    from app.core.idempotency import store_idempotent_response

    request = _make_request(None)
    _run(store_idempotent_response(request, "k", {"a": 1}))


def test_store_idempotent_response_writes_with_default_ttl() -> None:
    """Default TTL (24 h = 86400) is used when none is provided."""
    from app.core.idempotency import store_idempotent_response

    redis = MagicMock()
    redis.setex = AsyncMock()
    request = _make_request(redis)
    payload = {"id": 1, "ok": True}

    _run(store_idempotent_response(request, "key-1", payload))

    redis.setex.assert_awaited_once_with(
        "idempotency:key-1", 86_400, json.dumps(payload, default=str)
    )


def test_store_idempotent_response_uses_custom_ttl() -> None:
    """A caller-supplied TTL is forwarded to ``setex``."""
    from app.core.idempotency import store_idempotent_response

    redis = MagicMock()
    redis.setex = AsyncMock()
    request = _make_request(redis)

    _run(store_idempotent_response(request, "key-2", {"x": 1}, ttl=60))

    args, _ = redis.setex.call_args
    assert args[0] == "idempotency:key-2"
    assert args[1] == 60


def test_store_idempotent_response_serialises_non_json_via_default_str() -> None:
    """Non-JSON-native values (e.g. objects) are coerced via ``default=str``."""
    from app.core.idempotency import store_idempotent_response

    class Custom:
        def __str__(self) -> str:
            return "custom-value"

    redis = MagicMock()
    redis.setex = AsyncMock()
    request = _make_request(redis)

    _run(store_idempotent_response(request, "k", {"obj": Custom()}))

    args, _ = redis.setex.call_args
    assert "custom-value" in args[2]


def test_store_idempotent_response_swallows_redis_errors() -> None:
    """Redis errors during write are silently swallowed."""
    from app.core.idempotency import store_idempotent_response

    redis = MagicMock()
    redis.setex = AsyncMock(side_effect=RuntimeError("redis down"))
    request = _make_request(redis)

    _run(store_idempotent_response(request, "k", {"a": 1}))
