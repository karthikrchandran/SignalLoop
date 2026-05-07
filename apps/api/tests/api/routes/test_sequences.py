"""Tests for ``app.api.routes.sequences`` endpoints (Group E coverage)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
    SequenceStep,
)
from app.domain_models import Campaign, Contact, ContactProgression, ContactProgressionState

WORKSPACE_ID = "ws-sequences-test"
OTHER_WORKSPACE_ID = "ws-sequences-other"


def _headers(
    token_headers: dict[str, str], *, ws: str = WORKSPACE_ID, idem: bool = True
) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": ws}
    if idem:
        headers["Idempotency-Key"] = f"seq-{uuid.uuid4()}"
    return headers


@pytest.fixture()
def campaign(db: Session) -> Campaign:
    c = Campaign(
        name=f"Seq {uuid.uuid4().hex[:6]}",
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
def sequence(db: Session, campaign: Campaign) -> EmailSequence:
    s = EmailSequence(
        campaign_id=campaign.id,
        name="Welcome Drip",
        created_by=uuid.uuid4(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_sequence_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Admin POST /sequences returns SequencePublic for the new sequence."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/",
        headers=_headers(superuser_token_headers),
        json={"name": "Outreach", "campaign_id": str(campaign.id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Outreach"
    assert body["campaign_id"] == str(campaign.id)


def test_create_sequence_unknown_campaign_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Create against unknown campaign returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/",
        headers=_headers(superuser_token_headers),
        json={"name": "X", "campaign_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


def test_create_sequence_cross_workspace_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    other_campaign: Campaign,
) -> None:
    """Cross-workspace campaign reference returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/",
        headers=_headers(superuser_token_headers, ws=WORKSPACE_ID),
        json={"name": "X", "campaign_id": str(other_campaign.id)},
    )
    assert resp.status_code == 404


def test_create_sequence_missing_idempotency_400(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Missing Idempotency-Key returns 400 IDEMPOTENCY_KEY_REQUIRED."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/",
        headers=_headers(superuser_token_headers, idem=False),
        json={"name": "X", "campaign_id": str(campaign.id)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_create_sequence_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Operator POST returns 403."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/",
        headers=_headers(normal_user_token_headers),
        json={"name": "X", "campaign_id": str(campaign.id)},
    )
    assert resp.status_code == 403


def test_create_sequence_invalid_payload_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Missing required fields gives 422."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/",
        headers=_headers(superuser_token_headers),
        json={"name": "Only-name"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


def test_list_sequences_returns_workspace_data(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """List returns at least the seeded sequence."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(s["id"] == str(sequence.id) for s in body["data"])


def test_list_sequences_filter_by_campaign(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """campaign_id query param scopes the list."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/?campaign_id={sequence.campaign_id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    assert all(s["campaign_id"] == str(sequence.campaign_id) for s in resp.json()["data"])


def test_list_sequences_other_workspace_isolated(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """Listing from another workspace cannot see this sequence."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/",
        headers={**superuser_token_headers, "X-Workspace-Id": OTHER_WORKSPACE_ID},
    )
    assert resp.status_code == 200
    assert all(s["id"] != str(sequence.id) for s in resp.json()["data"])


def test_get_sequence_detail(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """GET /sequences/{id} returns SequenceDetailPublic with steps list."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{sequence.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(sequence.id)
    assert isinstance(body["steps"], list)


def test_get_sequence_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Unknown sequence id returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


def test_get_sequence_cross_workspace_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """Cross-workspace fetch returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{sequence.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": OTHER_WORKSPACE_ID},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update / steps / delete
# ---------------------------------------------------------------------------


def test_update_sequence_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """PUT updates name."""
    resp = client.put(
        f"{settings.API_V1_STR}/sequences/{sequence.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
        json={"name": "Renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


def test_update_sequence_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT unknown returns 404."""
    resp = client.put(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
        json={"name": "Nope"},
    )
    assert resp.status_code == 404


def test_update_sequence_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """Operator PUT returns 403."""
    resp = client.put(
        f"{settings.API_V1_STR}/sequences/{sequence.id}",
        headers={**normal_user_token_headers, "X-Workspace-Id": WORKSPACE_ID},
        json={"name": "Denied"},
    )
    assert resp.status_code == 403


def test_update_steps_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """PUT /steps replaces step list and returns SequenceDetailPublic with steps."""
    payload = {
        "steps": [
            {"step_order": 1, "delay_days": 0, "subject_template": "Hi", "body_template": "Hello"},
            {"step_order": 2, "delay_days": 3, "subject_template": "Follow", "body_template": "FollowUp"},
        ]
    }
    resp = client.put(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/steps",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
        json=payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["steps"]) == 2
    assert [s["step_order"] for s in body["steps"]] == [1, 2]


def test_update_steps_unknown_sequence_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /steps for unknown sequence returns 404."""
    resp = client.put(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}/steps",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
        json={"steps": []},
    )
    assert resp.status_code == 404


def test_delete_sequence_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign: Campaign,
) -> None:
    """DELETE removes the sequence and returns a success message."""
    s = EmailSequence(campaign_id=campaign.id, name="ToDelete", created_by=uuid.uuid4())
    db.add(s)
    db.commit()
    db.refresh(s)

    resp = client.delete(
        f"{settings.API_V1_STR}/sequences/{s.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "Sequence deleted"}


def test_delete_sequence_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """DELETE unknown returns 404."""
    resp = client.delete(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Enroll
# ---------------------------------------------------------------------------


def test_enroll_contacts_returns_count(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    sequence: EmailSequence,
    campaign: Campaign,
) -> None:
    """Enroll a campaign contact via ContactProgression and expect enrolled>=1."""
    contact = Contact(
        workspace_id=WORKSPACE_ID,
        email=f"enroll-{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(contact)
    db.flush()
    progression = ContactProgression(
        contact_id=contact.id,
        campaign_id=campaign.id,
        current_state=ContactProgressionState.inbox,
    )
    db.add(progression)
    db.commit()

    resp = client.post(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/enroll/{campaign.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enrolled"] >= 1
    assert "Enrolled" in body["message"]


def test_enroll_unknown_sequence_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Enroll with unknown sequence id returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}/enroll/{campaign.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


def test_enroll_unknown_campaign_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """Enroll with unknown campaign id returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/enroll/{uuid.uuid4()}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


def test_enroll_sequence_campaign_mismatch_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
    db: Session,
) -> None:
    """Enroll with mismatched sequence/campaign in the same workspace returns 404."""
    other = Campaign(
        name="Mismatch", workspace_id=WORKSPACE_ID, created_by=uuid.uuid4()
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    resp = client.post(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/enroll/{other.id}",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Progress / contacts
# ---------------------------------------------------------------------------


def test_get_progress_returns_breakdown(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    sequence: EmailSequence,
) -> None:
    """Progress endpoint returns total_steps and status_breakdown keys."""
    step = SequenceStep(
        sequence_id=sequence.id,
        step_order=1,
        delay_days=0,
        subject_template="s",
        body_template="b",
    )
    db.add(step)
    contact = Contact(workspace_id=WORKSPACE_ID, email=f"p-{uuid.uuid4().hex[:6]}@x.com")
    db.add(contact)
    db.flush()
    state = ContactSequenceState(
        contact_id=contact.id,
        sequence_id=sequence.id,
        status=SequenceStatus.active,
        current_step=1,
    )
    db.add(state)
    db.commit()

    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/progress",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sequence_id"] == str(sequence.id)
    assert body["total_steps"] >= 1
    assert body["total_enrolled"] >= 1
    assert isinstance(body["status_breakdown"], dict)
    assert isinstance(body["step_progress"], list)


def test_get_progress_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Progress for unknown sequence returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}/progress",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404


def test_get_contacts_paginated(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    sequence: EmailSequence,
) -> None:
    """Contacts endpoint returns paginated data array and count."""
    contact = Contact(workspace_id=WORKSPACE_ID, email=f"c-{uuid.uuid4().hex[:6]}@x.com")
    db.add(contact)
    db.flush()
    state = ContactSequenceState(
        contact_id=contact.id,
        sequence_id=sequence.id,
        status=SequenceStatus.active,
        current_step=2,
        next_send_at=datetime.now(timezone.utc),
    )
    db.add(state)
    db.commit()

    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/contacts?skip=0&limit=10",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "count" in body
    assert any(item["contact_id"] == str(contact.id) for item in body["data"])


def test_get_contacts_filter_by_status(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """Status filter narrows to that status (may be empty but must be 200)."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/contacts?status=stopped",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 200


def test_get_contacts_invalid_limit_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    sequence: EmailSequence,
) -> None:
    """limit > 100 fails Query validation (422)."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{sequence.id}/contacts?limit=500",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 422


def test_get_contacts_unknown_sequence_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Unknown sequence id returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/sequences/{uuid.uuid4()}/contacts",
        headers={**superuser_token_headers, "X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 404
