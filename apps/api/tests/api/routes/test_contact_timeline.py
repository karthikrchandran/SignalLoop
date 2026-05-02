"""API tests for the contact timeline endpoints (Story 5.1)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain_models import Campaign, Contact, ContactEvent, RoutingDecision

WORKSPACE_ID = "ws-story-5-1"
OTHER_WORKSPACE_ID = "ws-story-5-1-other"


def _headers(token_headers: dict[str, str]) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": WORKSPACE_ID}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def campaign_and_contact(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a campaign + contact for timeline tests; return (campaign_id, contact_id)."""
    campaign = Campaign(
        name="Timeline Test Campaign",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(campaign)

    contact = Contact(
        email=f"timeline-test-{uuid.uuid4().hex[:6]}@example.com",
        workspace_id=WORKSPACE_ID,
    )
    db.add(contact)
    db.commit()
    db.refresh(campaign)
    db.refresh(contact)
    return campaign.id, contact.id


@pytest.fixture()
def seeded_timeline(db: Session, campaign_and_contact: tuple[uuid.UUID, uuid.UUID]):
    """Seed ContactEvent and RoutingDecision rows for timeline tests."""
    campaign_id, contact_id = campaign_and_contact
    now = datetime.now(timezone.utc)

    events = [
        ContactEvent(
            contact_id=contact_id,
            campaign_id=campaign_id,
            workspace_id=WORKSPACE_ID,
            event_type="email_sent",
            channel="email",
            actor="system",
            outcome="delivered",
            reason_code="high_intent",
            template_ref="onboarding_v2",
            created_at=now,
        ),
        ContactEvent(
            contact_id=contact_id,
            campaign_id=campaign_id,
            workspace_id=WORKSPACE_ID,
            event_type="email_opened",
            channel="email",
            created_at=now,
        ),
        RoutingDecision(
            contact_id=contact_id,
            campaign_id=campaign_id,
            workspace_id=WORKSPACE_ID,
            decision_type="routing",
            outcome="sequence_assigned",
            reason_code="low_engagement",
            rule_name="re-engagement rule",
            rule_condition="opens < 2 AND days_since_sent > 7",
            signal_summary="Low open rate; high bounce risk",
            confidence_tier="medium",
            created_at=now,
        ),
    ]
    for e in events:
        db.add(e)
    db.commit()
    return campaign_id, contact_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_timeline_returns_events_for_contact(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Timeline endpoint aggregates events from multiple sources."""
    _campaign_id, contact_id = seeded_timeline
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "count" in body
    assert body["count"] >= 2  # at least the seeded rows
    ids = [e["id"] for e in body["data"]]
    # Should contain at least one ce_ and one rd_ event
    assert any(i.startswith("ce_") for i in ids)
    assert any(i.startswith("rd_") for i in ids)


def test_timeline_filter_by_event_type(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Filtering by event_type narrows the result set."""
    _campaign_id, contact_id = seeded_timeline
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
        params={"event_type": "email_sent"},
    )
    assert response.status_code == 200
    body = response.json()
    for event in body["data"]:
        assert event["event_type"] == "email_sent"


def test_timeline_cross_workspace_access_denied(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """A contact in WORKSPACE_ID is not visible when the header uses another workspace."""
    _campaign_id, contact_id = seeded_timeline
    other_headers = {**superuser_token_headers, "X-Workspace-Id": OTHER_WORKSPACE_ID}
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=other_headers,
    )
    # Contact belongs to WORKSPACE_ID, not OTHER_WORKSPACE_ID → 404
    assert response.status_code == 404


def test_timeline_event_detail_routing_decision(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Detail endpoint returns rule_condition and signal_summary for routing decisions."""
    _campaign_id, contact_id = seeded_timeline
    # Get full list first
    list_response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
    )
    assert list_response.status_code == 200
    events = list_response.json()["data"]
    rd_event = next((e for e in events if e["id"].startswith("rd_")), None)
    assert rd_event is not None, "Expected at least one routing_decision event"

    detail_response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline/{rd_event['id']}",
        headers=_headers(superuser_token_headers),
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["rule_name"] == "re-engagement rule"
    assert "opens < 2" in detail["rule_condition"]
    assert detail["signal_summary"] == "Low open rate; high bounce risk"
    assert detail["confidence_tier"] == "medium"


def test_timeline_event_detail_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Unknown event_id returns 404."""
    _campaign_id, contact_id = seeded_timeline
    fake_id = f"ce_{uuid.uuid4().hex}"
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline/{fake_id}",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 404
