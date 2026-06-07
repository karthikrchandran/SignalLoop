"""Tests for ``app.core.idempotency`` Redis-backed dedup helpers."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import BaseModel


def _run(coro):
    return asyncio.run(coro)


def _make_request(redis_client) -> MagicMock:
    """Build a minimal ``Request`` stub exposing ``app.state.redis_manager.client``."""
    request = MagicMock()
    request.app.state.redis_manager.client = redis_client
    request.method = "POST"
    request.url.path = "/api/v1/test"
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


# ---------------------------------------------------------------------------
# run_idempotent_mutation
# ---------------------------------------------------------------------------


def test_run_idempotent_mutation_stores_completed_response() -> None:
    from app.core.idempotency import run_idempotent_mutation

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock()
    request = _make_request(redis)

    result = _run(
        run_idempotent_mutation(
            request,
            idempotency_key="idem-1",
            workspace_id="ws",
            operation="op",
            mutation=lambda: {"ok": True},
            request_payload={"a": 1},
        )
    )

    assert result == {"ok": True}
    redis.set.assert_awaited_once()
    redis.setex.assert_awaited_once()
    stored = json.loads(redis.setex.await_args.args[2])
    assert stored["state"] == "completed"
    assert stored["response_data"] == {"ok": True}


def test_run_idempotent_mutation_encodes_response_models_for_replay() -> None:
    from app.core.idempotency import run_idempotent_mutation

    class ResponseModel(BaseModel):
        id: uuid.UUID
        action_at: datetime

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock()
    request = _make_request(redis)
    response = ResponseModel(id=uuid.uuid4(), action_at=datetime.now(UTC))

    result = _run(
        run_idempotent_mutation(
            request,
            idempotency_key="idem-1",
            workspace_id="ws",
            operation="op",
            mutation=lambda: response,
        )
    )

    assert result == response
    stored = json.loads(redis.setex.await_args.args[2])
    assert stored["response_data"] == {
        "id": str(response.id),
        "action_at": response.action_at.isoformat().replace("+00:00", "Z"),
    }


def test_run_idempotent_mutation_replays_completed_response() -> None:
    from app.core.idempotency import idempotency_request_hash, run_idempotent_mutation

    request = _make_request(None)
    request_hash = idempotency_request_hash(
        method="POST",
        path="/api/v1/test",
        payload={"a": 1},
    )
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "state": "completed",
                "request_hash": request_hash,
                "response_data": {"ok": True},
            }
        )
    )
    request.app.state.redis_manager.client = redis
    mutation = AsyncMock(return_value={"ok": False})

    result = _run(
        run_idempotent_mutation(
            request,
            idempotency_key="idem-1",
            workspace_id="ws",
            operation="op",
            mutation=mutation,
            request_payload={"a": 1},
        )
    )

    assert result == {"ok": True}
    mutation.assert_not_awaited()


def test_run_idempotent_mutation_rejects_key_reused_for_different_payload() -> None:
    from app.core.idempotency import idempotency_request_hash, run_idempotent_mutation

    request = _make_request(None)
    request_hash = idempotency_request_hash(
        method="POST",
        path="/api/v1/test",
        payload={"a": 1},
    )
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "state": "completed",
                "request_hash": request_hash,
                "response_data": {"ok": True},
            }
        )
    )
    request.app.state.redis_manager.client = redis

    with pytest.raises(HTTPException) as exc_info:
        _run(
            run_idempotent_mutation(
                request,
                idempotency_key="idem-1",
                workspace_id="ws",
                operation="op",
                mutation=lambda: {"ok": False},
                request_payload={"a": 2},
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_run_idempotent_mutation_rejects_in_progress_request() -> None:
    from app.core.idempotency import idempotency_request_hash, run_idempotent_mutation

    request_hash = idempotency_request_hash(
        method="POST",
        path="/api/v1/test",
        payload={"a": 1},
    )
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "state": "in_progress",
                "request_hash": request_hash,
            }
        )
    )
    request = _make_request(redis)

    with pytest.raises(HTTPException) as exc_info:
        _run(
            run_idempotent_mutation(
                request,
                idempotency_key="idem-1",
                workspace_id="ws",
                operation="op",
                mutation=lambda: {"ok": False},
                request_payload={"a": 1},
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"


def test_run_idempotent_mutation_fails_open_when_redis_missing() -> None:
    from app.core.idempotency import run_idempotent_mutation

    request = _make_request(None)

    result = _run(
        run_idempotent_mutation(
            request,
            idempotency_key="idem-1",
            workspace_id="ws",
            operation="op",
            mutation=lambda: {"ok": True},
        )
    )

    assert result == {"ok": True}
