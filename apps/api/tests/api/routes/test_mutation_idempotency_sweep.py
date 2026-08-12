"""HTTP idempotency coverage for remaining high-risk SignalLoop mutations."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.outreach.action_queue_service import write_dead_letter
from app.domain_models import (
    ActionQueue,
    Contact,
    DeadLetterEvent,
    IdempotencyRecord,
    ProviderCredential,
)

WORKSPACE_ID = "ws-idempotency-sweep"


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture()
def fake_idempotency_redis(client: TestClient) -> Generator[_FakeRedis, None, None]:
    original = getattr(client.app.state, "redis_manager", None)
    redis = _FakeRedis()
    client.app.state.redis_manager = SimpleNamespace(client=redis)
    try:
        yield redis
    finally:
        if original is None:
            del client.app.state.redis_manager
        else:
            client.app.state.redis_manager = original


def _headers(token_headers: dict[str, str], key: str | None = None) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": WORKSPACE_ID}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _request() -> MagicMock:
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/idempotency-test"
    return request


def test_safe_failure_is_durable_and_requires_explicit_retry(db: Session) -> None:
    from app.core.idempotency import run_idempotent_mutation

    key = f"safe-failure-{uuid.uuid4()}"
    with pytest.raises(RuntimeError):
        asyncio.run(
            run_idempotent_mutation(
                _request(),
                session=db,
                workspace_id=WORKSPACE_ID,
                operation="safe-failure",
                idempotency_key=key,
                request_payload={"x": 1},
                safe_to_retry_on_failure=True,
                mutation=lambda: (_ for _ in ()).throw(RuntimeError("before effect")),
            )
        )
    record = db.exec(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    ).one()
    assert record.state == "retryable_failure"
    retried = asyncio.run(
        run_idempotent_mutation(
            _request(),
            session=db,
            workspace_id=WORKSPACE_ID,
            operation="safe-failure",
            idempotency_key=key,
            request_payload={"x": 1},
            mutation=lambda: {"ok": True},
        )
    )
    replayed = asyncio.run(
        run_idempotent_mutation(
            _request(),
            session=db,
            workspace_id=WORKSPACE_ID,
            operation="safe-failure",
            idempotency_key=key,
            request_payload={"x": 1},
            mutation=lambda: {"unexpected": True},
        )
    )
    assert retried == replayed == {"ok": True}


def test_unknown_and_stale_claims_require_reconciliation(db: Session) -> None:
    from datetime import timedelta

    from app.core.idempotency import idempotency_request_hash, run_idempotent_mutation

    for state, lease in (
        ("unknown", None),
        ("in_progress", datetime.now(timezone.utc) - timedelta(seconds=1)),
    ):
        key = f"{state}-{uuid.uuid4()}"
        db.add(
            IdempotencyRecord(
                workspace_id=WORKSPACE_ID,
                operation="reconcile",
                idempotency_key=key,
                request_hash=idempotency_request_hash(
                    method="POST", path="/api/v1/idempotency-test", payload={}
                ),
                state=state,
                lease_expires_at=lease,
            )
        )
        db.commit()
        with pytest.raises(Exception) as blocked:
            asyncio.run(
                run_idempotent_mutation(
                    _request(),
                    session=db,
                    workspace_id=WORKSPACE_ID,
                    operation="reconcile",
                    idempotency_key=key,
                    mutation=lambda: {"unexpected": True},
                )
            )
        assert (
            blocked.value.detail["error"]["code"]
            == "IDEMPOTENCY_RECONCILIATION_REQUIRED"
        )


def _campaign(client: TestClient, token_headers: dict[str, str]) -> str:
    response = client.post(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(token_headers, f"campaign-{uuid.uuid4()}"),
        json={"name": f"Idempotency {uuid.uuid4()}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_provider_credential_mutation_replays_conflicts_and_requires_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    fake_idempotency_redis: _FakeRedis,
) -> None:
    _ = fake_idempotency_redis
    url = f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-credentials"
    payload = {"provider": "smtp", "channel": "email", "api_key": "key-one"}
    headers = _headers(superuser_token_headers, f"credential-replay-{uuid.uuid4()}")

    first = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)
    conflict = client.post(url, headers=headers, json={**payload, "api_key": "key-two"})
    missing = client.post(url, headers=_headers(superuser_token_headers), json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert missing.status_code == 400
    assert missing.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    replayed = db.get(ProviderCredential, uuid.UUID(first.json()["id"]))
    assert replayed is not None and replayed.is_active


def test_provider_credential_replays_from_durable_record_when_redis_is_unavailable(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """A Redis outage cannot re-run a completed provider mutation."""
    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = SimpleNamespace(client=None)
    try:
        url = f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-credentials"
        headers = _headers(superuser_token_headers, f"durable-outage-{uuid.uuid4()}")
        payload = {"provider": "smtp", "channel": "sms", "api_key": "outage-key"}
        first = client.post(url, headers=headers, json=payload)
        replay = client.post(url, headers=headers, json=payload)
    finally:
        client.app.state.redis_manager = original

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    active = db.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == WORKSPACE_ID,
            ProviderCredential.channel == "sms",
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).all()
    assert len(active) == 1


def test_runtime_config_mutation_replays_conflicts_and_requires_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_idempotency_redis: _FakeRedis,
) -> None:
    _ = fake_idempotency_redis
    url = f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/runtime-config"
    payload = {"team_notification_email": "ops@example.com"}
    headers = _headers(superuser_token_headers, f"runtime-replay-{uuid.uuid4()}")

    first = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)
    conflict = client.post(
        url, headers=headers, json={"team_notification_email": "other@example.com"}
    )
    missing = client.post(url, headers=_headers(superuser_token_headers), json=payload)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert missing.status_code == 400


def test_dead_letter_mutation_replays_conflicts_and_requires_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    fake_idempotency_redis: _FakeRedis,
) -> None:
    _ = fake_idempotency_redis
    campaign_id = _campaign(client, superuser_token_headers)
    contact = Contact(
        email=f"dead-{uuid.uuid4()}@example.com", workspace_id=WORKSPACE_ID
    )
    db.add(contact)
    db.commit()
    action = ActionQueue(
        workspace_id=WORKSPACE_ID,
        contact_id=contact.id,
        campaign_id=uuid.UUID(campaign_id),
        action_type="send_email",
        channel="email",
        payload={},
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.commit()
    write_dead_letter(
        db, action=action, failure_reason="timeout", workspace_id=WORKSPACE_ID
    )
    url = (
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters/{action.id}/retry"
    )
    headers = _headers(superuser_token_headers, f"dead-letter-replay-{uuid.uuid4()}")

    first = client.post(url, headers=headers)
    replay = client.post(url, headers=headers)
    missing = client.post(url, headers=_headers(superuser_token_headers))
    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert missing.status_code == 400
    retried = db.exec(
        select(DeadLetterEvent).where(
            DeadLetterEvent.action_queue_id == action.id,
            DeadLetterEvent.event_type == "retried",
        )
    ).all()
    assert len(retried) == 1


def test_campaign_strategy_segment_mutations_replay_conflict_and_require_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_idempotency_redis: _FakeRedis,
) -> None:
    _ = fake_idempotency_redis
    campaign_id = _campaign(client, superuser_token_headers)
    segment_url = f"{settings.API_V1_STR}/campaigns/{campaign_id}/segments"
    payload = {"name": "Priority", "rules": []}
    headers = _headers(superuser_token_headers, f"segment-replay-{uuid.uuid4()}")

    first = client.post(segment_url, headers=headers, json=payload)
    replay = client.post(segment_url, headers=headers, json=payload)
    conflict = client.post(
        segment_url, headers=headers, json={**payload, "name": "Changed"}
    )
    missing = client.post(
        segment_url, headers=_headers(superuser_token_headers), json=payload
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert missing.status_code == 400

    strategy_url = f"{settings.API_V1_STR}/campaigns/{campaign_id}/strategy"
    strategy_payload = {"channel_strategy": {"channel": "email", "cadence": "weekly"}}
    strategy_headers = _headers(
        superuser_token_headers, f"strategy-replay-{uuid.uuid4()}"
    )
    strategy_first = client.post(
        strategy_url, headers=strategy_headers, json=strategy_payload
    )
    strategy_replay = client.post(
        strategy_url, headers=strategy_headers, json=strategy_payload
    )
    strategy_conflict = client.post(
        strategy_url,
        headers=strategy_headers,
        json={"channel_strategy": {"channel": "sms", "cadence": "daily"}},
    )
    strategy_missing = client.post(
        strategy_url, headers=_headers(superuser_token_headers), json=strategy_payload
    )
    assert strategy_first.status_code == 200
    assert strategy_replay.json() == strategy_first.json()
    assert strategy_conflict.status_code == 409
    assert strategy_missing.status_code == 400
