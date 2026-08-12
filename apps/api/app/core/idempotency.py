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
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain_models import IdempotencyRecord

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
    session: Session | None = None,
    request_payload: Any = None,
    ttl: int = IDEMPOTENCY_TTL_SECONDS,
    in_progress_ttl: int = IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS,
    safe_to_retry_on_failure: bool = False,
) -> Any:
    """Run a mutation once using a durable database claim.

    Redis is deliberately not authoritative: a restart or cache write failure
    cannot permit a duplicate external side effect.  Claim/persist failures
    fail closed; an incomplete durable claim returns a retry-safe 409.
    """
    _ = ttl
    if session is None:
        raise HTTPException(
            status_code=503, detail="Durable idempotency storage unavailable"
        )
    request_hash = idempotency_request_hash(
        method=request.method,
        path=request.url.path,
        payload=request_payload,
    )

    existing = session.exec(
        select(IdempotencyRecord).where(
            IdempotencyRecord.workspace_id == workspace_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
    ).first()
    if existing:
        if (
            existing.state == "retryable_failure"
            and existing.request_hash == request_hash
        ):
            existing.state = "in_progress"
            existing.failure_reason = None
            existing.lease_expires_at = datetime.now(UTC) + timedelta(
                seconds=in_progress_ttl
            )
            session.add(existing)
            session.commit()
            record = existing
        else:
            return _durable_replay_or_raise(existing, request_hash, operation, session)
    else:
        record = IdempotencyRecord(
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=in_progress_ttl),
        )
        session.add(record)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.exec(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.workspace_id == workspace_id,
                    IdempotencyRecord.operation == operation,
                    IdempotencyRecord.idempotency_key == idempotency_key,
                )
            ).first()
            if existing:
                return _durable_replay_or_raise(
                    existing, request_hash, operation, session
                )
            raise HTTPException(
                status_code=503, detail="Durable idempotency claim failed"
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise HTTPException(
                status_code=503, detail="Durable idempotency claim failed"
            ) from exc

    try:
        response_data = await _maybe_await(mutation())
    except Exception as exc:
        _mark_failure(
            session,
            record.id,
            "retryable_failure" if safe_to_retry_on_failure else "unknown",
            type(exc).__name__,
        )
        raise
    record = session.get(IdempotencyRecord, record.id)
    if record is None:
        raise HTTPException(status_code=503, detail="Durable idempotency record lost")
    record.state = "completed"
    record.response_data = jsonable_encoder(response_data)
    record.completed_at = datetime.now(UTC)
    session.add(record)
    try:
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        _mark_failure(session, record.id, "unknown", "completion_persistence_failed")
        raise HTTPException(
            status_code=503, detail="Durable idempotency response persistence failed"
        ) from exc
    return response_data


def _durable_replay_or_raise(
    record: IdempotencyRecord, request_hash: str, operation: str, session: Session
) -> Any:
    if record.request_hash != request_hash:
        _raise_idempotency_conflict(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key was already used for a different request",
            {},
        )
    if record.state == "completed":
        return record.response_data
    if (
        record.state == "in_progress"
        and record.lease_expires_at
        and record.lease_expires_at <= datetime.now(UTC)
    ):
        record.state = "unknown"
        record.failure_reason = "lease_expired_requires_reconciliation"
        session.add(record)
        session.commit()
    if record.state == "unknown":
        _raise_idempotency_conflict(
            "IDEMPOTENCY_RECONCILIATION_REQUIRED",
            "The prior request outcome is unknown; reconcile before retrying",
            {"operation": operation},
        )
    _raise_idempotency_conflict(
        "IDEMPOTENCY_IN_PROGRESS",
        "A request with this Idempotency-Key is already in progress",
        {"operation": operation},
    )


def _mark_failure(session: Session, record_id: Any, state: str, reason: str) -> None:
    """Best-effort durable terminal state; never release an uncertain claim."""
    try:
        record = session.get(IdempotencyRecord, record_id)
        if record is None:
            return
        record.state = state
        record.failure_reason = reason
        record.lease_expires_at = None
        session.add(record)
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()


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
