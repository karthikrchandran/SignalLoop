from __future__ import annotations

from collections.abc import Generator
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


WORKSPACE_ID = "ws-story-1-3"


def _headers(token_headers: dict[str, str], *, idempotency: bool = False) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": WORKSPACE_ID}
    if idempotency:
        headers["Idempotency-Key"] = f"templates-{uuid.uuid4()}"
    return headers


def _template_payload(content: str, subject: str | None = "Hello {{contact.firstName}}") -> dict[str, object]:
    return {
        "name": "Lifecycle Email",
        "channel": "email",
        "subject": subject,
        "content": content,
        "tokens": [
            {
                "name": "contact.firstName",
                "source_field": "contact.firstName",
                "default_value": "there",
                "fallback_behavior": "defaultValue",
            }
        ],
    }


class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture()
def fake_idempotency_redis(client: TestClient) -> Generator[_FakeRedisClient, None, None]:
    original = getattr(client.app.state, "redis_manager", None)
    redis = _FakeRedisClient()

    class _Manager:
        client = redis

    client.app.state.redis_manager = _Manager()
    try:
        yield redis
    finally:
        if original is None:
            del client.app.state.redis_manager
        else:
            client.app.state.redis_manager = original


def test_create_template_replays_same_idempotency_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_idempotency_redis: _FakeRedisClient,
) -> None:
    headers = _headers(superuser_token_headers, idempotency=True)
    body = _template_payload("Hi {{contact.firstName}}. Please unsubscribe anytime.")
    body["name"] = f"Replay template {uuid.uuid4()}"

    first = client.post(f"{settings.API_V1_STR}/templates/", headers=headers, json=body)
    second = client.post(f"{settings.API_V1_STR}/templates/", headers=headers, json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    listed = client.get(f"{settings.API_V1_STR}/templates/", headers=superuser_token_headers | {"X-Workspace-Id": WORKSPACE_ID})
    matches = [row for row in listed.json()["data"] if row["name"] == body["name"]]
    assert len(matches) == 1


def test_create_template_rejects_reused_idempotency_key_with_different_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_idempotency_redis: _FakeRedisClient,
) -> None:
    headers = _headers(superuser_token_headers, idempotency=True)
    body = _template_payload("One unsubscribe line.")
    body["name"] = "Conflict template"
    changed = {**body, "name": "Conflict template changed"}

    first = client.post(f"{settings.API_V1_STR}/templates/", headers=headers, json=body)
    second = client.post(f"{settings.API_V1_STR}/templates/", headers=headers, json=changed)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_template_publish_blocked_when_guardrails_fail(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=_headers(superuser_token_headers, idempotency=True),
        json=_template_payload("Guaranteed results for {{contact.firstName}}."),
    )
    assert create_response.status_code == 200
    template = create_response.json()

    publish_response = client.post(
        f"{settings.API_V1_STR}/templates/{template['id']}/versions/{template['current_version']['id']}/publish",
        headers=_headers(superuser_token_headers, idempotency=True),
    )
    assert publish_response.status_code == 400
    detail = publish_response.json()["detail"]
    reason_codes = {item["reason_code"] for item in detail}
    assert "MISSING_REQUIRED_DISCLAIMER" in reason_codes
    assert "BANNED_PHRASE_PRESENT" in reason_codes


def test_published_template_remains_immutable_by_creating_new_draft_version(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    compliant_content = "Hi {{contact.firstName}}. Please use the unsubscribe link below."

    create_response = client.post(
        f"{settings.API_V1_STR}/templates/",
        headers=_headers(superuser_token_headers, idempotency=True),
        json=_template_payload(compliant_content),
    )
    assert create_response.status_code == 200
    template = create_response.json()

    publish_response = client.post(
        f"{settings.API_V1_STR}/templates/{template['id']}/versions/{template['current_version']['id']}/publish",
        headers=_headers(superuser_token_headers, idempotency=True),
    )
    assert publish_response.status_code == 200
    published_template = publish_response.json()
    assert published_template["current_version"]["status"] == "published"
    assert published_template["current_version"]["version_number"] == 1

    patch_response = client.patch(
        f"{settings.API_V1_STR}/templates/{template['id']}",
        headers=_headers(superuser_token_headers, idempotency=True),
        json={"content": "Updated content with unsubscribe included."},
    )
    assert patch_response.status_code == 200
    patched_template = patch_response.json()
    assert patched_template["current_version"]["version_number"] == 2
    assert patched_template["current_version"]["status"] == "draft"
