"""API tests for the contact timeline endpoints (Story 5.1)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest, SchedulingStatus
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import (
    Campaign,
    Contact,
    ContactEvent,
    ContactProgressionState,
    ContactStateHistory,
    RoutingDecision,
)

WORKSPACE_ID = "ws-story-5-1"
OTHER_WORKSPACE_ID = "ws-story-5-1-other"


def _headers(token_headers: dict[str, str]) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": WORKSPACE_ID}


def _install_redis_client(client: TestClient, redis_client):
    had_original = hasattr(client.app.state, "redis_manager")
    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = SimpleNamespace(client=redis_client)
    return had_original, original


def _restore_redis_client(client: TestClient, had_original: bool, original) -> None:
    if had_original:
        client.app.state.redis_manager = original
        return
    try:
        del client.app.state.redis_manager
    except AttributeError:
        pass


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
    """Seed rows from every Story 5.1 timeline source."""
    campaign_id, contact_id = campaign_and_contact
    now = datetime.now(timezone.utc).replace(microsecond=0)

    state_history = ContactStateHistory(
        contact_id=contact_id,
        campaign_id=campaign_id,
        workspace_id=WORKSPACE_ID,
        from_state=ContactProgressionState.inbox,
        to_state=ContactProgressionState.engaged,
        reason="campaign_enrolled",
        triggered_at=now - timedelta(minutes=6),
    )
    db.add(state_history)

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
            event_metadata={
                "reason_code_explanation": "Contact matched the high intent rule."
            },
            created_at=now - timedelta(minutes=5),
        ),
        ContactEvent(
            contact_id=contact_id,
            campaign_id=campaign_id,
            workspace_id=WORKSPACE_ID,
            event_type="email_opened",
            channel="email",
            created_at=now - timedelta(minutes=4),
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
            created_at=now - timedelta(minutes=3),
        ),
    ]
    for e in events:
        db.add(e)

    signal = SignalEvent(
        workspace_id=WORKSPACE_ID,
        contact_id=contact_id,
        campaign_id=campaign_id,
        channel="email",
        signal_type="high_intent",
        confidence=0.91,
        signal_metadata={"summary": "Clicked pricing twice"},
        created_at=now - timedelta(minutes=2),
    )
    db.add(signal)
    db.flush()

    db.add(
        SchedulingRequest(
            workspace_id=WORKSPACE_ID,
            contact_id=contact_id,
            campaign_id=campaign_id,
            signal_event_id=signal.id,
            status=SchedulingStatus.booked,
            created_at=now - timedelta(minutes=1),
        )
    )

    script = VoiceScript(
        campaign_id=campaign_id,
        name="Timeline Script",
        content="Hello from SignalLoop",
        created_by=uuid.uuid4(),
        created_at=now - timedelta(minutes=1),
        updated_at=now - timedelta(minutes=1),
    )
    db.add(script)
    db.flush()
    call_request = CallRequest(
        workspace_id=WORKSPACE_ID,
        contact_id=contact_id,
        campaign_id=campaign_id,
        voice_script_id=script.id,
        trigger_reason="positive_email_signal",
        scheduled_at=now - timedelta(seconds=30),
        created_at=now - timedelta(seconds=30),
    )
    db.add(call_request)
    db.flush()
    db.add(
        CallSession(
            call_request_id=call_request.id,
            twilio_status="completed",
            twilio_status_updated_at=now,
            outcome=CallOutcome.answered,
            transcript="Buyer said they want a demo next Tuesday morning.",
            created_at=now,
        )
    )
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
    assert any(i.startswith("ce_") for i in ids)
    assert any(i.startswith("rd_") for i in ids)
    assert any(i.startswith("csh_") for i in ids)
    assert any(i.startswith("sig_") for i in ids)
    assert any(i.startswith("sched_") for i in ids)
    assert any(i.startswith("call_") for i in ids)

    timestamps = [event["timestamp"] for event in body["data"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_timeline_orders_equal_timestamps_by_distinct_event_id(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    campaign_and_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Events with the same timestamp are ordered by id for stable cursor paging."""
    campaign_id, contact_id = campaign_and_contact
    shared_timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    lower_id = uuid.uuid4()
    higher_id = uuid.uuid4()
    if lower_id.hex > higher_id.hex:
        lower_id, higher_id = higher_id, lower_id

    db.add(
        ContactEvent(
            id=lower_id,
            contact_id=contact_id,
            campaign_id=campaign_id,
            workspace_id=WORKSPACE_ID,
            event_type="email_sent",
            channel="email",
            created_at=shared_timestamp,
        )
    )
    db.add(
        ContactEvent(
            id=higher_id,
            contact_id=contact_id,
            campaign_id=campaign_id,
            workspace_id=WORKSPACE_ID,
            event_type="email_opened",
            channel="email",
            created_at=shared_timestamp,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
    )

    assert response.status_code == 200
    assert [event["id"] for event in response.json()["data"]] == [
        f"ce_{higher_id.hex}",
        f"ce_{lower_id.hex}",
    ]


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


def test_timeline_filter_by_multiple_event_types(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Comma-separated event_type filters support the UI multi-select."""
    _campaign_id, contact_id = seeded_timeline
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
        params={"event_type": "email_sent,booking_event"},
    )
    assert response.status_code == 200
    body = response.json()
    assert {event["event_type"] for event in body["data"]} == {
        "email_sent",
        "booking_event",
    }


def test_timeline_date_filter_includes_full_to_day(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Date range filters include events through the selected end day."""
    _campaign_id, contact_id = seeded_timeline
    today = datetime.now(timezone.utc).date().isoformat()
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
        params={"from": f"{today}T00:00:00Z", "to": f"{today}T23:59:59.999Z"},
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 6


def test_timeline_cursor_pagination_has_no_duplicate_events(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Cursor pagination returns the next slice without duplicating the first page."""
    _campaign_id, contact_id = seeded_timeline
    first = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
        params={"limit": 2},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["next_cursor"]

    second = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
        params={"limit": 2, "cursor": first_body["next_cursor"]},
    )
    assert second.status_code == 200
    first_ids = {event["id"] for event in first_body["data"]}
    second_ids = {event["id"] for event in second.json()["data"]}
    assert first_ids.isdisjoint(second_ids)


def test_timeline_first_page_cache_hit_uses_cached_count(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign_and_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """The first unfiltered page can be served from Redis with stored total metadata."""
    _campaign_id, contact_id = campaign_and_contact
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "data": [
                    {
                        "id": "ce_11111111111111111111111111111111",
                        "source_system": "contact_events",
                        "event_type": "email_sent",
                        "channel": "email",
                        "timestamp": "2026-05-06T14:30:00Z",
                        "actor": "system",
                        "outcome": "sent",
                        "reason_code": "high_intent",
                        "has_detail": True,
                    }
                ],
                "count": 250,
            }
        )
    )
    redis.setex = AsyncMock()
    had_original, original = _install_redis_client(client, redis)

    try:
        response = client.get(
            f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
            headers=_headers(superuser_token_headers),
        )
    finally:
        _restore_redis_client(client, had_original, original)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 250
    assert body["data"][0]["event_type"] == "email_sent"
    redis.get.assert_awaited_once_with(f"timeline:{contact_id.hex}:all:page1")
    redis.setex.assert_not_awaited()


def test_timeline_first_page_cache_stores_real_total_above_200(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    campaign_and_contact: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Large timelines report the true total while caching only the bounded first window."""
    campaign_id, contact_id = campaign_and_contact
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for index in range(205):
        db.add(
            ContactEvent(
                contact_id=contact_id,
                campaign_id=campaign_id,
                workspace_id=WORKSPACE_ID,
                event_type="email_sent",
                channel="email",
                created_at=now - timedelta(seconds=index),
            )
        )
    db.commit()

    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    had_original, original = _install_redis_client(client, redis)

    try:
        response = client.get(
            f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
            headers=_headers(superuser_token_headers),
            params={"limit": 50},
        )
    finally:
        _restore_redis_client(client, had_original, original)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 205
    assert len(body["data"]) == 50
    assert body["next_cursor"]
    redis.setex.assert_awaited_once()
    args = redis.setex.await_args.args
    assert args[0] == f"timeline:{contact_id.hex}:all:page1"
    cached_payload = json.loads(args[2])
    assert cached_payload["count"] == 205
    assert len(cached_payload["data"]) == 200


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


def test_timeline_rejects_cross_workspace_campaign_filter(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """A valid contact cannot be queried with another workspace's campaign_id."""
    _campaign_id, contact_id = seeded_timeline
    other_campaign = Campaign(
        name="Other Workspace Campaign",
        workspace_id=OTHER_WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(other_campaign)
    db.commit()
    db.refresh(other_campaign)

    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
        params={"campaign_id": str(other_campaign.id)},
    )
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
    assert detail["reason_code_explanation"] == "Low open rate; high bounce risk"


def test_timeline_event_detail_contact_event_explanation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Contact event detail exposes reason-code explanation metadata."""
    _campaign_id, contact_id = seeded_timeline
    list_response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
    )
    assert list_response.status_code == 200
    event = next(e for e in list_response.json()["data"] if e["event_type"] == "email_sent")
    assert event["has_detail"] is True

    detail_response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline/{event['id']}",
        headers=_headers(superuser_token_headers),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["reason_code_explanation"] == (
        "Contact matched the high intent rule."
    )


def test_timeline_event_detail_call_transcript(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Voice call detail includes the stored transcript excerpt."""
    _campaign_id, contact_id = seeded_timeline
    list_response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline",
        headers=_headers(superuser_token_headers),
    )
    assert list_response.status_code == 200
    event = next(e for e in list_response.json()["data"] if e["id"].startswith("call_"))

    detail_response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline/{event['id']}",
        headers=_headers(superuser_token_headers),
    )
    assert detail_response.status_code == 200
    assert "demo next Tuesday" in detail_response.json()["transcript_excerpt"]


def test_timeline_event_bad_id_returns_400(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    seeded_timeline: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Invalid event id syntax returns 400 instead of leaking an exception."""
    _campaign_id, contact_id = seeded_timeline
    response = client.get(
        f"{settings.API_V1_STR}/contacts/{contact_id}/timeline/not-a-prefixed-uuid",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 400


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
