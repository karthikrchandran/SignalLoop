"""Tests for ``app.api.routes.dashboard`` endpoints (Group E coverage)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain_models import Campaign

WORKSPACE_ID = "ws-dashboard-test"
OTHER_WORKSPACE_ID = "ws-dashboard-other"


def _headers(token_headers: dict[str, str], ws: str = WORKSPACE_ID) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": ws}


@pytest.fixture()
def campaign(db: Session) -> Campaign:
    c = Campaign(
        name=f"Dashboard {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_email_metrics_admin_returns_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Admin GET email-metrics returns the expected dict shape."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{campaign.id}/email-metrics",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("total_enrolled", "active", "completed", "stopped", "sent", "failed"):
        assert key in body


def test_email_metrics_unknown_campaign_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Email-metrics for missing campaign id returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{uuid.uuid4()}/email-metrics",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


def test_email_metrics_cross_workspace_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Querying another workspace must not leak the campaign — returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{campaign.id}/email-metrics",
        headers=_headers(superuser_token_headers, ws=OTHER_WORKSPACE_ID),
    )
    assert resp.status_code == 404


def test_call_metrics_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Admin GET call-metrics returns the expected aggregate shape."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{campaign.id}/call-metrics",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "total_queued",
        "in_progress",
        "completed",
        "failed",
        "answered",
        "voicemail",
        "no_answer",
    ):
        assert key in body


def test_call_metrics_missing_campaign_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Call-metrics for unknown campaign returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{uuid.uuid4()}/call-metrics",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


def test_signal_summary_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Admin GET signals returns a dict (possibly empty)."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{campaign.id}/signals",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_signal_summary_missing_campaign_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Signals for unknown campaign returns 404."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{uuid.uuid4()}/signals",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


def test_daily_cap_status_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Daily cap status returns the four documented counters."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/daily-cap-status",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "email_sent_today",
        "email_daily_cap",
        "call_initiated_today",
        "call_daily_cap",
    ):
        assert key in body


def test_daily_cap_status_requires_workspace_header(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Missing X-Workspace-Id returns the WORKSPACE_REQUIRED 400 envelope."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/daily-cap-status",
        headers=superuser_token_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "WORKSPACE_REQUIRED"


def test_dashboard_routes_reject_non_admin(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """All dashboard endpoints require admin → operator gets 403."""
    paths = [
        f"/dashboard/campaigns/{campaign.id}/email-metrics",
        f"/dashboard/campaigns/{campaign.id}/call-metrics",
        f"/dashboard/campaigns/{campaign.id}/signals",
        "/dashboard/daily-cap-status",
    ]
    for path in paths:
        resp = client.get(
            f"{settings.API_V1_STR}{path}",
            headers=_headers(normal_user_token_headers),
        )
        assert resp.status_code == 403, path


def test_dashboard_unauthenticated(client: TestClient, campaign: Campaign) -> None:
    """Unauthenticated requests are rejected (401)."""
    resp = client.get(
        f"{settings.API_V1_STR}/dashboard/campaigns/{campaign.id}/email-metrics",
        headers={"X-Workspace-Id": WORKSPACE_ID},
    )
    assert resp.status_code == 401
