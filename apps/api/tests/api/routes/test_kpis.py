"""API tests for the KPI summary and trend endpoints (Story 5.4)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.domain_models import Campaign, Contact, ActionQueue

WORKSPACE_ID = "ws-story-5-4"
OTHER_WORKSPACE_ID = "ws-other-5-4"


def _headers(token_headers: dict[str, str], ws: str = WORKSPACE_ID) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": ws}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def campaign(db: Session) -> Campaign:
    c = Campaign(
        name=f"KPI Test {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def contact(db: Session) -> Contact:
    c = Contact(
        email=f"kpi-test-{uuid.uuid4().hex[:6]}@example.com",
        workspace_id=WORKSPACE_ID,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def action(db: Session, campaign: Campaign, contact: Contact) -> ActionQueue:
    a = ActionQueue(
        contact_id=contact.id,
        campaign_id=campaign.id,
        action_type="send_email",
        channel="email",
        payload={},
        status="completed",
        retry_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Auth / workspace enforcement
# ---------------------------------------------------------------------------


def test_summary_requires_auth(client: TestClient) -> None:
    """Unauthenticated requests must be rejected."""
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/summary",
        params={"start": "2024-01-01", "end": "2024-01-31", "granularity": "weekly"},
        headers={"X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 401


def test_trend_requires_auth(client: TestClient) -> None:
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/trend",
        params={"start": "2024-01-01", "end": "2024-01-31", "granularity": "weekly"},
        headers={"X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 401


def test_summary_workspace_mismatch_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Non-superuser whose header workspace differs from path param must get 403."""
    resp = client.get(
        f"/api/v1/workspaces/{OTHER_WORKSPACE_ID}/kpis/summary",
        params={"start": "2024-01-01", "end": "2024-01-31", "granularity": "weekly"},
        headers=_headers(normal_user_token_headers, ws=WORKSPACE_ID),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Superuser: happy-path response shape
# ---------------------------------------------------------------------------


def test_summary_response_shape(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Summary endpoint must return current_period, prior_period, and delta_pct."""
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/summary",
        params={"start": "2024-01-01", "end": "2024-01-31", "granularity": "weekly"},
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "current_period" in data
    assert "prior_period" in data
    assert "delta_pct" in data

    for section in ("current_period", "prior_period", "delta_pct"):
        for field in (
            "contacts_processed",
            "intent_signals",
            "qualified_contacts",
            "bookings_confirmed",
            "provider_errors",
            "signal_yield_rate",
            "conversion_rate",
            "booking_sla_compliance_pct",
        ):
            assert field in data[section], f"Missing {field} in {section}"


def test_trend_response_is_list(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Trend endpoint must return a JSON array."""
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/trend",
        params={"start": "2024-01-01", "end": "2024-01-31", "granularity": "weekly"},
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_trend_bucket_shape(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Each trend bucket must contain period_start, period_end, and core KPI fields."""
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/trend",
        params={"start": "2024-01-01", "end": "2024-03-31", "granularity": "monthly"},
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    buckets = resp.json()
    if buckets:
        b = buckets[0]
        for field in ("period_start", "period_end", "contacts_processed", "signal_yield_rate"):
            assert field in b, f"Missing {field} in trend bucket"


def test_summary_invalid_dates_returns_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """start > end must be rejected with 422."""
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/summary",
        params={"start": "2024-03-01", "end": "2024-01-01", "granularity": "weekly"},
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 422


def test_summary_optional_campaign_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Passing a campaign_id filter must return 200 with valid shape."""
    resp = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/kpis/summary",
        params={
            "start": "2024-01-01",
            "end": "2024-01-31",
            "granularity": "weekly",
            "campaign_id": str(campaign.id),
        },
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    assert "current_period" in resp.json()
