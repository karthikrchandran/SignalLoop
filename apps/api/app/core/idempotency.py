"""Idempotency deduplication backed by Redis.

Usage in a route
----------------
    cached = await check_idempotency(request, idempotency_key)
    if cached is not None:
        return cached

    # ... perform mutation ...

    await store_idempotent_response(request, idempotency_key, result.model_dump())
    return result
"""
from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder

IDEMPOTENCY_TTL_SECONDS = 86_400
IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS = 300


async def check_idempotency(request: Request, idempotency_key: str) -> Any | None:
    """Return the cached response dict if this key has been seen before, else None."""
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return None
        cached = await redis.get(f"idempotency:{idempotency_key}")
        if cached:
            return json.loads(cached)
    except Exception:  # noqa: BLE001 — Redis errors must never break the request path
        pass
    return None


async def store_idempotent_response(
    request: Request,
    idempotency_key: str,
    response_data: Any,
    ttl: int = 86_400,
) -> None:
    """Persist the serialised response in Redis keyed by idempotency key (default TTL: 24 h)."""
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return
        await redis.setex(
            f"idempotency:{idempotency_key}",
            ttl,
            json.dumps(response_data, default=str),
        )
    except Exception:  # noqa: BLE001
        pass


def idempotency_request_hash(
    *,
    method: str,
    path: str,
    payload: Any = None,
) -> str:
    """Return a stable hash for an idempotent mutation request."""
    normalized = json.dumps(
        {
            "method": method.upper(),
            "path": path,
            "payload": payload if payload is not None else {},
        },
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def idempotency_storage_key(
    *,
    workspace_id: str,
    operation: str,
    idempotency_key: str,
) -> str:
    """Namespace an idempotency key by tenant and mutation operation."""
    return f"idempotency:v2:{workspace_id}:{operation}:{idempotency_key}"


async def run_idempotent_mutation(
    request: Request,
    *,
    idempotency_key: str,
    workspace_id: str,
    operation: str,
    mutation: Callable[[], Any],
    request_payload: Any = None,
    ttl: int = IDEMPOTENCY_TTL_SECONDS,
    in_progress_ttl: int = IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS,
) -> Any:
    """Run a mutation once for a workspace/operation/idempotency key.

    Same key + same request hash replays the stored response. Same key with a
    different request hash returns 409. Concurrent duplicates return 409 while
    the first request is in progress. Redis outages fail open so local/demo
    environments can still operate without Redis.
    """
    redis = _redis_client(request)
    if redis is None:
        return await _maybe_await(mutation())

    storage_key = idempotency_storage_key(
        workspace_id=workspace_id,
        operation=operation,
        idempotency_key=idempotency_key,
    )
    request_hash = idempotency_request_hash(
        method=request.method,
        path=request.url.path,
        payload=request_payload,
    )

    try:
        existing = await _read_record(redis, storage_key)
        replay = _replay_or_raise(existing, request_hash)
        if replay is not _NO_REPLAY:
            return replay

        in_progress = json.dumps(
            {"state": "in_progress", "request_hash": request_hash},
            default=str,
        )
        created = await redis.set(
            storage_key,
            in_progress,
            ex=in_progress_ttl,
            nx=True,
        )
        if not created:
            existing = await _read_record(redis, storage_key)
            replay = _replay_or_raise(existing, request_hash)
            if replay is not _NO_REPLAY:
                return replay
            _raise_idempotency_conflict(
                "IDEMPOTENCY_IN_PROGRESS",
                "A request with this Idempotency-Key is already in progress",
                {"operation": operation},
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        return await _maybe_await(mutation())

    try:
        response_data = await _maybe_await(mutation())
    except Exception:
        await _delete_record(redis, storage_key)
        raise

    try:
        await redis.setex(
            storage_key,
            ttl,
            json.dumps(
                {
                    "state": "completed",
                    "request_hash": request_hash,
                    "response_data": jsonable_encoder(response_data),
                },
                default=str,
            ),
        )
    except Exception:  # noqa: BLE001
        pass
    return response_data


_NO_REPLAY = object()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _redis_client(request: Request) -> Any | None:
    try:
        redis_manager = getattr(request.app.state, "redis_manager", None)
        return getattr(redis_manager, "client", None)
    except Exception:  # noqa: BLE001
        return None


async def _read_record(redis: Any, storage_key: str) -> dict[str, Any] | None:
    raw = await redis.get(storage_key)
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


async def _delete_record(redis: Any, storage_key: str) -> None:
    try:
        await redis.delete(storage_key)
    except Exception:  # noqa: BLE001
        pass


def _replay_or_raise(existing: dict[str, Any] | None, request_hash: str) -> Any:
    if not existing:
        return _NO_REPLAY
    if existing.get("request_hash") != request_hash:
        _raise_idempotency_conflict(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key was already used for a different request",
            {},
        )
    if existing.get("state") == "completed":
        return existing.get("response_data")
    if existing.get("state") == "in_progress":
        _raise_idempotency_conflict(
            "IDEMPOTENCY_IN_PROGRESS",
            "A request with this Idempotency-Key is already in progress",
            {},
        )
    return _NO_REPLAY


def _raise_idempotency_conflict(
    code: str,
    message: str,
    details: dict[str, Any],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": {
                "code": code,
                "message": message,
                "semantic": "POLICY_VIOLATION",
                "details": details,
            }
        },
    )
