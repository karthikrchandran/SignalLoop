from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings


WORKSPACE_ID = "ws-story-1-3"


def _headers(token_headers: dict[str, str], *, idempotency: bool = False) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": WORKSPACE_ID}
    if idempotency:
        headers["Idempotency-Key"] = "test-idempotency-key"
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
