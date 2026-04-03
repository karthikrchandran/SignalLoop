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

import json
from typing import Any

from fastapi import Request


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
