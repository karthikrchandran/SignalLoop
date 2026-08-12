"""API tests for the campaign health and dead-letter visibility endpoints (Story 5.3)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.outreach.action_queue_service import write_dead_letter
from app.domain_models import ActionQueue, Campaign, Contact, DeadLetterEvent

WORKSPACE_ID = "ws-story-5-3"


def _headers(token_headers: dict[str, str]) -> dict[str, str]:
    return {
        **token_headers,
        "X-Workspace-Id": WORKSPACE_ID,
        "Idempotency-Key": f"dead-letter-{uuid.uuid4()}",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def campaign_contact(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """Create campaign + contact for health tests."""
    campaign = Campaign(
        name=f"Health Test {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    contact = Contact(
        email=f"health-test-{uuid.uuid4().hex[:6]}@example.com",
        workspace_id=WORKSPACE_ID,
    )
    db.add(campaign)
    db.add(contact)
    db.commit()
    db.refresh(campaign)
    db.refresh(contact)
    return campaign.id, contact.id


def _make_action(
    db: Session,
    campaign_id: uuid.UUID,
    contact_id: uuid.UUID,
    *,
    status: str = "pending",
    retry_count: int = 0,
) -> ActionQueue:
    action = ActionQueue(
        workspace_id=WORKSPACE_ID,
        contact_id=contact_id,
        campaign_id=campaign_id,
        action_type="send_email",
        channel="email",
        payload={},
        status=status,
        retry_count=retry_count,
        created_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


# ---------------------------------------------------------------------------
# Unit tests — write_dead_letter service function
# ---------------------------------------------------------------------------


def test_write_dead_letter_inserts_event_synchronously(
    db: Session, campaign_contact: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """Story 5.3 Task 3 — DeadLetterEvent row is written synchronously inside the same tx."""
    campaign_id, contact_id = campaign_contact
    action = _make_action(db, campaign_id, contact_id)

    write_dead_letter(
        db,
        action=action,
        failure_reason="SMTP timeout",
        workspace_id=WORKSPACE_ID,
    )

    # action status updated
    assert action.status == "dead_letter"
    assert action.failure_reason == "SMTP timeout"
    assert action.dead_lettered_at is not None

    # DeadLetterEvent row persisted immediately (same transaction)
    dle = db.exec(
        select(DeadLetterEvent).where(DeadLetterEvent.action_queue_id == action.id)
    ).first()
    assert dle is not None
    assert dle.event_type == "dead_lettered"
    assert dle.failure_reason == "SMTP timeout"
    assert dle.workspace_id == WORKSPACE_ID


# ---------------------------------------------------------------------------
# Integration — GET /campaigns/{id}/health
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_dead_letter_count(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Health snapshot correctly reflects dead_letter items in the queue."""
    campaign_id, contact_id = campaign_contact
    action = _make_action(db, campaign_id, contact_id)
    write_dead_letter(
        db,
        action=action,
        failure_reason="provider down",
        workspace_id=WORKSPACE_ID,
    )

    response = client.get(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/health",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dead_letter_count"] >= 1


# ---------------------------------------------------------------------------
# Integration — GET /campaigns/{id}/dead-letters
# ---------------------------------------------------------------------------


def test_dead_letter_list_returns_items(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Dead-letter list endpoint shows items and retry eligibility."""
    campaign_id, contact_id = campaign_contact
    action = _make_action(db, campaign_id, contact_id, retry_count=0)
    write_dead_letter(
        db,
        action=action,
        failure_reason="bounce",
        workspace_id=WORKSPACE_ID,
    )

    response = client.get(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    item = next((i for i in body["data"] if i["id"] == str(action.id)), None)
    assert item is not None
    assert item["retry_eligible"] is True  # retry_count=0 < MAX_RETRY_COUNT


def test_campaign_health_and_dead_letter_actions_filter_direct_workspace_owner(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    campaign_id, contact_id = campaign_contact
    cross_attached = ActionQueue(
        workspace_id="workspace-b",
        contact_id=contact_id,
        campaign_id=campaign_id,
        action_type="send_email",
        channel="email",
        status="dead_letter",
        retry_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(cross_attached)
    if db.get_bind().dialect.name == "postgresql":
        with pytest.raises(SQLAlchemyError):
            db.commit()
        db.rollback()
        return
    db.commit()

    listed = client.get(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters",
        headers=_headers(superuser_token_headers),
    )
    assert listed.status_code == 200
    assert str(cross_attached.id) not in {row["id"] for row in listed.json()["data"]}

    retried = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters/{cross_attached.id}/retry",
        headers=_headers(superuser_token_headers),
    )
    dismissed = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters/{cross_attached.id}/dismiss",
        headers=_headers(superuser_token_headers),
    )
    assert retried.status_code == 404
    assert dismissed.status_code == 404


# ---------------------------------------------------------------------------
# Integration — retry eligible item (POST …/retry)
# ---------------------------------------------------------------------------


def test_retry_resets_item_to_pending(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Retry clears dead_letter status and resets retry_count to 0."""
    campaign_id, contact_id = campaign_contact
    action = _make_action(db, campaign_id, contact_id, retry_count=1)
    write_dead_letter(
        db,
        action=action,
        failure_reason="timeout",
        workspace_id=WORKSPACE_ID,
    )

    response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters/{action.id}/retry",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["retry_count"] == 0

    db.refresh(action)
    assert action.status == "pending"
    assert action.retry_count == 0
    assert action.failure_reason is None


# ---------------------------------------------------------------------------
# Integration — retry ineligible item returns 422
# ---------------------------------------------------------------------------


def test_retry_ineligible_returns_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    campaign_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Retry attempt on max-retried item returns 422 RETRY_INELIGIBLE."""
    campaign_id, contact_id = campaign_contact
    action = _make_action(db, campaign_id, contact_id, retry_count=settings.MAX_RETRY_COUNT)
    write_dead_letter(
        db,
        action=action,
        failure_reason="repeated failure",
        workspace_id=WORKSPACE_ID,
    )

    response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/dead-letters/{action.id}/retry",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error"]["code"] == "RETRY_INELIGIBLE"
