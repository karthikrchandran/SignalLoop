"""Tests for ``app.api.routes.scripts`` endpoints (Group E coverage)."""
from __future__ import annotations

from collections.abc import Generator
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.voice.models import VoiceScript
from app.domain_models import Campaign

WORKSPACE_ID = "ws-scripts-test"
OTHER_WORKSPACE_ID = "ws-scripts-other"

SAMPLE_CONTENT = (
    "## Opening Pitch\nHello, this is your AI agent.\n\n"
    "## Q&A\nQ: Are you available?\nA: Yes I am.\n\n"
    "## Fallback\nLet me follow up.\n\n"
    "## Scheduling\nWhen are you free?\n"
)


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


def _headers(
    token_headers: dict[str, str], *, ws: str = WORKSPACE_ID, idem: bool = True
) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": ws}
    if idem:
        headers["Idempotency-Key"] = f"scripts-{uuid.uuid4()}"
    return headers


@pytest.fixture()
def campaign(db: Session) -> Campaign:
    c = Campaign(
        name=f"Scripts {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def other_campaign(db: Session) -> Campaign:
    c = Campaign(
        name=f"Other {uuid.uuid4().hex[:6]}",
        workspace_id=OTHER_WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def script(db: Session, campaign: Campaign) -> VoiceScript:
    s = VoiceScript(
        campaign_id=campaign.id,
        name="Pitch v1",
        content=SAMPLE_CONTENT,
        created_by=uuid.uuid4(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_script_admin_returns_public(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Admin POST /scripts returns ScriptPublic with the supplied name."""
    resp = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=_headers(superuser_token_headers),
        json={"name": "Outreach", "campaign_id": str(campaign.id), "content": SAMPLE_CONTENT},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Outreach"
    assert body["campaign_id"] == str(campaign.id)


def test_create_script_unknown_campaign_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Create against unknown campaign returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=_headers(superuser_token_headers),
        json={"name": "X", "campaign_id": str(uuid.uuid4()), "content": SAMPLE_CONTENT},
    )
    assert resp.status_code == 404


def test_create_script_cross_workspace_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    other_campaign: Campaign,
) -> None:
    """Create script for campaign in another workspace returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=_headers(superuser_token_headers, ws=WORKSPACE_ID),
        json={"name": "X", "campaign_id": str(other_campaign.id), "content": SAMPLE_CONTENT},
    )
    assert resp.status_code == 404


def test_create_script_missing_idempotency_400(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Create without Idempotency-Key returns IDEMPOTENCY_KEY_REQUIRED."""
    resp = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=_headers(superuser_token_headers, idem=False),
        json={"name": "X", "campaign_id": str(campaign.id), "content": SAMPLE_CONTENT},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_create_script_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Operator POST /scripts returns 403."""
    resp = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=_headers(normal_user_token_headers),
        json={"name": "X", "campaign_id": str(campaign.id), "content": SAMPLE_CONTENT},
    )
    assert resp.status_code == 403


def test_create_script_invalid_payload_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Missing fields rejected with 422."""
    resp = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=_headers(superuser_token_headers),
        json={"name": "Only-name"},
    )
    assert resp.status_code == 422


def test_create_script_replays_same_idempotency_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
    fake_idempotency_redis: _FakeRedisClient,
) -> None:
    headers = {**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID, "Idempotency-Key": "scripts-replay"}
    script_name = f"Replay script {uuid.uuid4()}"
    payload = {
        "name": script_name,
        "campaign_id": str(campaign.id),
        "content": SAMPLE_CONTENT,
    }

    first = client.post(f"{settings.API_V1_STR}/scripts/", headers=headers, json=payload)
    second = client.post(f"{settings.API_V1_STR}/scripts/", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    listed = client.get(
        f"{settings.API_V1_STR}/scripts/",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    matches = [row for row in listed.json()["data"] if row["name"] == script_name]
    assert len(matches) == 1


def test_create_script_rejects_reused_idempotency_key_with_different_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
    fake_idempotency_redis: _FakeRedisClient,
) -> None:
    headers = {**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID, "Idempotency-Key": "scripts-conflict"}
    payload = {
        "name": "Conflict script",
        "campaign_id": str(campaign.id),
        "content": SAMPLE_CONTENT,
    }

    first = client.post(f"{settings.API_V1_STR}/scripts/", headers=headers, json=payload)
    second = client.post(
        f"{settings.API_V1_STR}/scripts/",
        headers=headers,
        json={**payload, "name": "Conflict script changed"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_scripts_returns_workspace_scripts(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """List scripts returns the freshly-seeded script."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert any(s["id"] == str(script.id) for s in body["data"])


def test_list_scripts_filter_by_campaign(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """campaign_id query param scopes the list."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/?campaign_id={script.campaign_id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(s["campaign_id"] == str(script.campaign_id) for s in body["data"])


def test_list_scripts_other_workspace_isolated(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """Listing from another workspace must not see this script."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/",
        headers={**superuser_token_headers, "X-Workspace-Id": OTHER_WORKSPACE_ID},
    )
    assert resp.status_code == 200
    assert all(s["id"] != str(script.id) for s in resp.json()["data"])


# ---------------------------------------------------------------------------
# Get / preview
# ---------------------------------------------------------------------------


def test_get_script_returns_detail(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """GET /scripts/{id} returns ScriptDetailPublic with parsed content."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/{script.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(script.id)
    assert body["content"] == SAMPLE_CONTENT
    assert body["parsed"]["opening_pitch"]


def test_get_script_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Unknown script id returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/{uuid.uuid4()}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


def test_get_script_cross_workspace_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """Cross-workspace fetch returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/{script.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": OTHER_WORKSPACE_ID},
    )
    assert resp.status_code == 404


def test_preview_script(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """Preview returns parsed sections."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/{script.id}/preview",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["opening_pitch"]
    assert body["scheduling_question"]
    assert isinstance(body["qa_pairs"], list)


def test_preview_script_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Preview unknown script returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/scripts/{uuid.uuid4()}/preview",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update / delete
# ---------------------------------------------------------------------------


def test_update_script_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """PUT updates name and returns detail."""
    resp = client.put(
        f"{settings.API_V1_STR}/scripts/{script.id}",
        headers=_headers(superuser_token_headers),
        json={"name": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


def test_update_script_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT unknown script returns 404."""
    resp = client.put(
        f"{settings.API_V1_STR}/scripts/{uuid.uuid4()}",
        headers=_headers(superuser_token_headers),
        json={"name": "Nope"},
    )
    assert resp.status_code == 404


def test_update_script_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """Operator PUT returns 403."""
    resp = client.put(
        f"{settings.API_V1_STR}/scripts/{script.id}",
        headers={**normal_user_token_headers, "X-Workspace-Id": WORKSPACE_ID},
        json={"name": "Denied"},
    )
    assert resp.status_code == 403


def test_delete_script_marks_inactive(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign: Campaign,
) -> None:
    """DELETE deactivates the script (active=False)."""
    s = VoiceScript(
        campaign_id=campaign.id,
        name="To Delete",
        content=SAMPLE_CONTENT,
        created_by=uuid.uuid4(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    resp = client.delete(
        f"{settings.API_V1_STR}/scripts/{s.id}",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "Script deactivated"}
    db.refresh(s)
    assert s.active is False


def test_delete_script_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """DELETE unknown script returns 404."""
    resp = client.delete(
        f"{settings.API_V1_STR}/scripts/{uuid.uuid4()}",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


def test_delete_script_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    script: VoiceScript,
) -> None:
    """Operator DELETE returns 403."""
    resp = client.delete(
        f"{settings.API_V1_STR}/scripts/{script.id}",
        headers={**normal_user_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 403
