"""Tests for ``app.api.routes.controls`` endpoints (Group E coverage)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain_models import Campaign, CampaignStatus, GlobalControlState

WORKSPACE_ID = "ws-controls-test"
OTHER_WORKSPACE_ID = "ws-controls-other"


def _headers(token_headers: dict[str, str], *, ws: str = WORKSPACE_ID, idem: bool = True) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": ws}
    if idem:
        headers["Idempotency-Key"] = f"controls-{uuid.uuid4()}"
    return headers


@pytest.fixture()
def campaign(db: Session) -> Campaign:
    c = Campaign(
        name=f"Controls {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
        status=CampaignStatus.draft,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Global pause / resume
# ---------------------------------------------------------------------------


def test_pause_global_admin_creates_state(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Admin POST /controls/pause creates new GlobalControlState (paused=True)."""
    resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(superuser_token_headers),
        json={"paused_reason": "incident-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["paused"] is True
    assert body["paused_reason"] == "incident-1"
    assert body["action"] == "pause"


def test_pause_global_idempotent_updates_existing_state(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """Calling pause again updates the existing state (no duplicate row error)."""
    client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(superuser_token_headers),
        json={"paused_reason": "first"},
    )
    resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(superuser_token_headers),
        json={"paused_reason": "second"},
    )
    assert resp.status_code == 200
    assert resp.json()["paused_reason"] == "second"
    rows = db.exec(
        select(GlobalControlState).where(
            GlobalControlState.workspace_id == WORKSPACE_ID,
            GlobalControlState.campaign_id == None,
        )
    ).all()
    assert len(rows) == 1


def test_pause_global_missing_idempotency_returns_400(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Pause without Idempotency-Key returns IDEMPOTENCY_KEY_REQUIRED."""
    resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(superuser_token_headers, idem=False),
        json={"paused_reason": "missing-key"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_pause_global_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Operator attempting pause gets AUTH_ERROR 403."""
    resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(normal_user_token_headers),
        json={"paused_reason": "denied"},
    )
    assert resp.status_code == 403


def test_pause_global_unauthenticated(client: TestClient) -> None:
    """Unauthenticated pause returns 401."""
    resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers={"X-Workspace-Id": WORKSPACE_ID, "Idempotency-Key": "x"},
        json={"paused_reason": "anon"},
    )
    assert resp.status_code == 401


def test_pause_global_invalid_body_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Missing paused_reason field is rejected by pydantic (422)."""
    resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(superuser_token_headers),
        json={},
    )
    assert resp.status_code == 422


def test_resume_global_after_pause(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """After pause, resume clears flags and returns paused=False."""
    ws_headers = {
        **superuser_token_headers,
        "X-Workspace-Id": "ws-controls-resume",
        "Idempotency-Key": f"r-{uuid.uuid4()}",
    }
    pause_resp = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=ws_headers,
        json={"paused_reason": "for-resume"},
    )
    assert pause_resp.status_code == 200

    resume_headers = {
        **superuser_token_headers,
        "X-Workspace-Id": "ws-controls-resume",
        "Idempotency-Key": f"r2-{uuid.uuid4()}",
    }
    resp = client.post(
        f"{settings.API_V1_STR}/controls/resume",
        headers=resume_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["paused"] is False
    assert body["paused_reason"] is None
    assert body["action"] == "resume"


def test_resume_global_when_no_state_returns_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Resume when no global state exists returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/controls/resume",
        headers={
            **superuser_token_headers,
            "X-Workspace-Id": f"ws-no-state-{uuid.uuid4().hex[:6]}",
            "Idempotency-Key": "x",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Per-campaign pause / resume
# ---------------------------------------------------------------------------


def test_pause_campaign_admin_changes_status(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Admin pause campaign returns ControlStatePublic and flips status."""
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign.id}/pause",
        headers=_headers(superuser_token_headers),
        json={"paused_reason": "qa-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["paused"] is True


def test_pause_campaign_unknown_id_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Pause unknown campaign returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{uuid.uuid4()}/pause",
        headers=_headers(superuser_token_headers),
        json={"paused_reason": "missing"},
    )
    assert resp.status_code == 404


def test_pause_campaign_cross_workspace_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Pause attempt from another workspace cannot find the campaign (404)."""
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign.id}/pause",
        headers=_headers(superuser_token_headers, ws=OTHER_WORKSPACE_ID),
        json={"paused_reason": "isolation"},
    )
    assert resp.status_code == 404


def test_pause_campaign_non_admin_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Operator pause campaign returns 403."""
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign.id}/pause",
        headers=_headers(normal_user_token_headers),
        json={"paused_reason": "denied"},
    )
    assert resp.status_code == 403


def test_resume_campaign_after_pause(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    campaign: Campaign,
) -> None:
    """Pause then resume campaign returns paused=False and 200."""
    pr = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign.id}/pause",
        headers=_headers(superuser_token_headers),
        json={"paused_reason": "for-resume"},
    )
    assert pr.status_code == 200
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign.id}/resume",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    assert resp.json()["paused"] is False
    assert resp.json()["action"] == "resume"


def test_resume_campaign_without_pause_state_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """Resume on a campaign with no control state returns 404."""
    fresh = Campaign(
        name=f"Fresh {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(fresh)
    db.commit()
    db.refresh(fresh)
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{fresh.id}/resume",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


def test_resume_campaign_unknown_404(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Resume non-existent campaign returns 404."""
    resp = client.post(
        f"{settings.API_V1_STR}/campaigns/{uuid.uuid4()}/resume",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CC-5 uniqueness — partial-index constraint coverage
# ---------------------------------------------------------------------------


def test_pause_campaign_idempotent_no_duplicate_row(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """Calling campaign pause twice must not create a second GlobalControlState row
    for the same workspace+campaign pair (partial unique index enforced)."""
    ws = f"ws-cc5-camp-{uuid.uuid4().hex[:6]}"
    camp = Campaign(
        name=f"CC5 {uuid.uuid4().hex[:6]}",
        workspace_id=ws,
        created_by=uuid.uuid4(),
        status=CampaignStatus.draft,
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)

    headers1 = {**superuser_token_headers, "X-Workspace-Id": ws, "Idempotency-Key": f"cc5-1-{uuid.uuid4()}"}
    resp1 = client.post(
        f"{settings.API_V1_STR}/campaigns/{camp.id}/pause",
        headers=headers1,
        json={"paused_reason": "first-pause"},
    )
    assert resp1.status_code == 200

    headers2 = {**superuser_token_headers, "X-Workspace-Id": ws, "Idempotency-Key": f"cc5-2-{uuid.uuid4()}"}
    resp2 = client.post(
        f"{settings.API_V1_STR}/campaigns/{camp.id}/pause",
        headers=headers2,
        json={"paused_reason": "second-pause"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["paused_reason"] == "second-pause"

    rows = db.exec(
        select(GlobalControlState).where(
            GlobalControlState.workspace_id == ws,
            GlobalControlState.campaign_id == camp.id,
        )
    ).all()
    assert len(rows) == 1, "Duplicate GlobalControlState row detected — uniqueness constraint violated"


def test_global_and_campaign_states_are_independent(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """Global (workspace-level) pause and campaign-level pause produce separate
    GlobalControlState rows — they must not collide on the partial unique index."""
    ws = f"ws-cc5-indep-{uuid.uuid4().hex[:6]}"
    camp = Campaign(
        name=f"CC5Indep {uuid.uuid4().hex[:6]}",
        workspace_id=ws,
        created_by=uuid.uuid4(),
        status=CampaignStatus.draft,
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)

    gh = {**superuser_token_headers, "X-Workspace-Id": ws, "Idempotency-Key": f"cc5-g-{uuid.uuid4()}"}
    resp_global = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=gh,
        json={"paused_reason": "global-pause"},
    )
    assert resp_global.status_code == 200

    ch = {**superuser_token_headers, "X-Workspace-Id": ws, "Idempotency-Key": f"cc5-c-{uuid.uuid4()}"}
    resp_campaign = client.post(
        f"{settings.API_V1_STR}/campaigns/{camp.id}/pause",
        headers=ch,
        json={"paused_reason": "campaign-pause"},
    )
    assert resp_campaign.status_code == 200

    all_rows = db.exec(
        select(GlobalControlState).where(GlobalControlState.workspace_id == ws)
    ).all()
    assert len(all_rows) == 2, "Expected exactly 2 rows: one global and one campaign-scoped"
    campaign_ids = {r.campaign_id for r in all_rows}
    assert None in campaign_ids, "Global row (campaign_id=NULL) missing"
    assert camp.id in campaign_ids, "Campaign-scoped row missing"


def test_pause_same_workspace_different_campaigns_independent(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """Pausing two different campaigns under the same workspace creates two separate
    rows — one per campaign, no cross-contamination."""
    ws = f"ws-cc5-two-{uuid.uuid4().hex[:6]}"
    camp_a = Campaign(name=f"A-{uuid.uuid4().hex[:6]}", workspace_id=ws, created_by=uuid.uuid4())
    camp_b = Campaign(name=f"B-{uuid.uuid4().hex[:6]}", workspace_id=ws, created_by=uuid.uuid4())
    db.add(camp_a)
    db.add(camp_b)
    db.commit()
    db.refresh(camp_a)
    db.refresh(camp_b)

    for camp in (camp_a, camp_b):
        h = {**superuser_token_headers, "X-Workspace-Id": ws, "Idempotency-Key": f"cc5-ab-{uuid.uuid4()}"}
        resp = client.post(
            f"{settings.API_V1_STR}/campaigns/{camp.id}/pause",
            headers=h,
            json={"paused_reason": "multi-pause"},
        )
        assert resp.status_code == 200

    rows = db.exec(
        select(GlobalControlState).where(
            GlobalControlState.workspace_id == ws,
            GlobalControlState.campaign_id.in_([camp_a.id, camp_b.id]),  # type: ignore[attr-defined]
        )
    ).all()
    assert len(rows) == 2
    assert {r.campaign_id for r in rows} == {camp_a.id, camp_b.id}
