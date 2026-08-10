from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.voice.models import (
    CallRequest,
    CallRequestStatus,
    VoiceScript,
)
from app.domain_models import (
    Campaign,
    CampaignStatus,
    Contact,
    GlobalControlState,
    GovernancePolicy,
    PolicyStatus,
    PolicyType,
)
from worker_app import call_worker  # type: ignore[import-untyped]


def _database():  # noqa: ANN202
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _adapter(call_sid: str) -> MagicMock:
    adapter = MagicMock()
    adapter._account_sid = f"AC-{call_sid}"
    adapter.initiate_call = AsyncMock(return_value={"call_sid": call_sid})
    return adapter


def _sequence_adapter(*call_sids: str) -> MagicMock:
    adapter = MagicMock()
    adapter._account_sid = "AC-sequence"
    adapter.initiate_call = AsyncMock(
        side_effect=[{"call_sid": call_sid} for call_sid in call_sids]
    )
    return adapter


def _seed_call(session: Session, workspace_id: str, *, status: CallRequestStatus = CallRequestStatus.queued) -> CallRequest:
    campaign = Campaign(
        name=f"Campaign {workspace_id}",
        workspace_id=workspace_id,
        status=CampaignStatus.active,
        created_by=uuid.uuid4(),
    )
    contact = Contact(
        workspace_id=workspace_id,
        email=f"{workspace_id}@example.com",
        phone="+15551234567",
        timezone="UTC",
        consent_voice=True,
    )
    session.add(campaign)
    session.add(contact)
    session.flush()
    script = VoiceScript(
        campaign_id=campaign.id,
        name="Script",
        content="Hello",
        created_by=uuid.uuid4(),
    )
    session.add(script)
    session.flush()
    request = CallRequest(
        workspace_id=workspace_id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_queue",
        status=status,
        scheduled_at=datetime.now(UTC),
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def test_poll_dispatch_resolves_provider_for_each_stored_workspace() -> None:
    engine = _database()
    with Session(engine) as session:
        request_a = _seed_call(session, "workspace-a")
        request_b = _seed_call(session, "workspace-b")
        request_a_id = request_a.id
        request_b_id = request_b.id

    adapters = {
        "workspace-a": _adapter("CA-A"),
        "workspace-b": _adapter("CA-B"),
        "default": _sequence_adapter("CA-default-a", "CA-default-b"),
    }
    resolved_workspaces: list[str] = []

    def resolve_adapter(_session: Session, workspace_id: str, **_kwargs: object):
        resolved_workspaces.append(workspace_id)
        return adapters[workspace_id]

    with (
        patch.object(call_worker, "_engine", engine),
        patch.object(call_worker, "_is_within_call_hours", return_value=True),
        patch.object(call_worker, "resolve_voice_adapter", side_effect=resolve_adapter),
    ):
        asyncio.run(call_worker.poll_and_dispatch())

    with Session(engine) as session:
        request_a = session.get(CallRequest, request_a_id)
        request_b = session.get(CallRequest, request_b_id)
        assert request_a is not None
        assert request_b is not None
        assert request_a.status == CallRequestStatus.in_progress
        assert request_b.status == CallRequestStatus.in_progress
    assert resolved_workspaces == ["workspace-a", "workspace-b"]
    adapters["workspace-a"].initiate_call.assert_awaited_once()
    adapters["workspace-b"].initiate_call.assert_awaited_once()
    adapters["default"].initiate_call.assert_not_awaited()


def test_paused_or_capped_workspace_does_not_block_another_workspace() -> None:
    engine = _database()
    with Session(engine) as session:
        paused_request = _seed_call(session, "workspace-paused")
        capped_request = _seed_call(session, "workspace-capped")
        _seed_call(session, "workspace-capped", status=CallRequestStatus.in_progress)
        active_request = _seed_call(session, "workspace-active")
        paused_request_id = paused_request.id
        capped_request_id = capped_request.id
        active_request_id = active_request.id
        session.add(GlobalControlState(workspace_id="workspace-paused", paused=True))
        session.add(
            GovernancePolicy(
                workspace_id="workspace-capped",
                scope="workspace",
                policy_type=PolicyType.daily_caps,
                status=PolicyStatus.active,
                payload_json={"daily_call_cap": 1},
            )
        )
        session.commit()

    active_adapter = _sequence_adapter(
        "CA-paused",
        "CA-capped",
        "CA-active",
    )
    resolved_workspaces: list[str] = []

    def resolve_adapter(_session: Session, workspace_id: str, **_kwargs: object):
        resolved_workspaces.append(workspace_id)
        return active_adapter

    with (
        patch.object(call_worker, "_engine", engine),
        patch.object(call_worker, "_is_within_call_hours", return_value=True),
        patch.object(call_worker, "resolve_voice_adapter", side_effect=resolve_adapter),
    ):
        asyncio.run(call_worker.poll_and_dispatch())

    with Session(engine) as session:
        paused = session.get(CallRequest, paused_request_id)
        capped = session.get(CallRequest, capped_request_id)
        active = session.get(CallRequest, active_request_id)
        assert paused is not None
        assert capped is not None
        assert active is not None
        assert paused.status == CallRequestStatus.queued
        assert capped.status == CallRequestStatus.queued
        assert active.status == CallRequestStatus.in_progress
    assert resolved_workspaces == ["workspace-active"]
    active_adapter.initiate_call.assert_awaited_once()


def test_initiate_one_rejects_contact_from_another_workspace() -> None:
    engine = _database()
    adapter = _adapter("CA-cross-tenant")
    with Session(engine) as session:
        request = _seed_call(session, "workspace-a")
        contact = session.exec(
            select(Contact).where(Contact.id == request.contact_id)
        ).one()
        contact.workspace_id = "workspace-b"
        session.add(contact)
        session.commit()

        with patch.object(call_worker, "_is_within_call_hours", return_value=True):
            result = asyncio.run(
                call_worker._initiate_one(
                    session,
                    request,
                    workspace_id="workspace-a",
                    adapter=adapter,
                )
            )

        session.commit()
        session.refresh(request)
        assert request.status == CallRequestStatus.failed

    assert result is False
    adapter.initiate_call.assert_not_awaited()


def test_initiate_one_rejects_missing_campaign_and_cross_campaign_script() -> None:
    engine = _database()
    adapter = _adapter("CA-must-not-dispatch")
    with Session(engine) as session:
        request = _seed_call(session, "workspace-a")
        campaign = session.get(Campaign, request.campaign_id)
        assert campaign is not None
        session.delete(campaign)
        session.commit()
        with patch.object(call_worker, "_is_within_call_hours", return_value=True):
            result = asyncio.run(
                call_worker._initiate_one(
                    session, request, workspace_id="workspace-a", adapter=adapter
                )
            )
        session.commit()
        session.refresh(request)
        assert request.status == CallRequestStatus.failed
        assert result is False
    adapter.initiate_call.assert_not_awaited()

    engine = _database()
    adapter = _adapter("CA-must-not-dispatch-script")
    with Session(engine) as session:
        request = _seed_call(session, "workspace-a")
        other = _seed_call(session, "workspace-b")
        request.voice_script_id = other.voice_script_id
        session.add(request)
        session.commit()
        with patch.object(call_worker, "_is_within_call_hours", return_value=True):
            result = asyncio.run(
                call_worker._initiate_one(
                    session, request, workspace_id="workspace-a", adapter=adapter
                )
            )
        session.commit()
        session.refresh(request)
        assert request.status == CallRequestStatus.failed
        assert result is False
    adapter.initiate_call.assert_not_awaited()


def test_poll_dispatch_denies_missing_voice_consent_before_provider_resolution() -> None:
    engine = _database()
    with Session(engine) as session:
        request = _seed_call(session, "workspace-a")
        contact = session.get(Contact, request.contact_id)
        assert contact is not None
        contact.consent_voice = False
        session.add(contact)
        session.commit()
        request_id = request.id

    with (
        patch.object(call_worker, "_engine", engine),
        patch.object(call_worker, "_is_within_call_hours", return_value=True),
        patch.object(call_worker, "resolve_voice_adapter") as resolver,
    ):
        asyncio.run(call_worker.poll_and_dispatch())

    with Session(engine) as session:
        request = session.get(CallRequest, request_id)
        assert request is not None
        assert request.status == CallRequestStatus.failed
    resolver.assert_not_called()
