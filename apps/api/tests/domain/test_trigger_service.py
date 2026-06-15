"""Unit tests for ``app.domain.signals.trigger_service``."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.signals import trigger_service
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain.signals.trigger_service import (
    DEFAULT_RULES,
    get_trigger_rules,
    process_signal,
    set_trigger_enabled,
)
from app.domain.voice.models import CallRequest, VoiceScript
from app.domain_models import Campaign, Contact, OutboxEvent


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Per-test in-memory SQLite session."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


@pytest.fixture(autouse=True)
def reset_trigger_state() -> Generator[None, None, None]:
    """Reset module-level toggle state and patch external sinks."""
    original = dict(trigger_service._trigger_enabled)
    with patch.object(trigger_service, "append_audit_event", new=AsyncMock()):
        with patch.object(trigger_service, "SendGridAdapter") as adapter_cls:
            adapter_cls.return_value.send_email = AsyncMock(
                return_value={"status_code": 202, "message_id": "x"}
            )
            yield
    trigger_service._trigger_enabled.clear()
    trigger_service._trigger_enabled.update(original)


def _make_contact(session: Session, **overrides) -> Contact:
    defaults = {
        "workspace_id": "ws",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "A",
        "company": "Acme",
    }
    defaults.update(overrides)
    contact = Contact(**defaults)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def _make_campaign(session: Session, *, workspace_id: str = "ws") -> Campaign:
    campaign = Campaign(
        name="Campaign",
        created_by=uuid.uuid4(),
        workspace_id=workspace_id,
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


def _make_signal(
    session: Session,
    contact_id: uuid.UUID,
    *,
    signal_type: str,
    channel: str = "email",
    campaign_id: uuid.UUID | None = None,
) -> SignalEvent:
    sig = SignalEvent(
        contact_id=contact_id,
        campaign_id=campaign_id or uuid.uuid4(),
        channel=channel,
        signal_type=signal_type,
    )
    session.add(sig)
    session.commit()
    session.refresh(sig)
    return sig


def _make_voice_script(
    session: Session, campaign_id: uuid.UUID, active: bool = True
) -> VoiceScript:
    vs = VoiceScript(
        campaign_id=campaign_id,
        name="vs",
        content="x",
        active=active,
        created_by=uuid.uuid4(),
    )
    session.add(vs)
    session.commit()
    session.refresh(vs)
    return vs


class _CapturingEmailAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sent: list[dict] = []

    async def send_email(self, **kwargs):
        key = kwargs["idempotency_key"]
        intent = self.session.exec(
            select(OutboxEvent).where(OutboxEvent.idempotency_key == key)
        ).first()
        assert intent is not None
        assert intent.published_at is None
        self.sent.append(kwargs)
        return {"status_code": 202, "message_id": "msg-1"}


# ---------- process_signal: routing ----------


def test_process_signal_unknown_type_returns_empty(session: Session) -> None:
    """Signals without rules return [] without side effects."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="totally_unknown")
    result = _run(process_signal(session, sig))
    assert result == []


def test_process_signal_disabled_rule_returns_empty(session: Session) -> None:
    """When the rule is disabled, no actions execute."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="email_positive_reply")
    set_trigger_enabled("email_positive_reply", False)
    try:
        result = _run(process_signal(session, sig))
    finally:
        set_trigger_enabled("email_positive_reply", True)
    assert result == []


def test_process_signal_email_positive_reply_full_path(session: Session) -> None:
    """email_positive_reply queues followup call + sends demo email."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="email_positive_reply")
    _make_voice_script(session, sig.campaign_id, active=True)

    executed = _run(process_signal(session, sig))

    assert "queue_followup_call" in executed
    assert "send_demo_email" in executed
    calls = session.exec(select(CallRequest)).all()
    assert len(calls) == 1
    assert calls[0].contact_id == contact.id
    assert calls[0].trigger_reason == "positive_email_signal"


def test_process_signal_no_active_script_skips_call(session: Session) -> None:
    """No active VoiceScript -> queue_followup_call still reported but no row."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="email_positive_reply")
    _make_voice_script(session, sig.campaign_id, active=False)

    executed = _run(process_signal(session, sig))

    assert "queue_followup_call" in executed
    assert session.exec(select(CallRequest)).all() == []


def test_process_signal_send_demo_email_missing_contact(session: Session) -> None:
    """If contact is missing, send_demo_email returns silently."""
    sig = _make_signal(session, uuid.uuid4(), signal_type="email_positive_reply")
    executed = _run(process_signal(session, sig))
    assert "send_demo_email" in executed


def test_process_signal_scheduling_creates_request_and_emails_team(
    session: Session,
) -> None:
    """scheduling_requested creates SchedulingRequest and emails team if configured."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="scheduling_requested")

    with patch.object(trigger_service.settings, "TEAM_NOTIFICATION_EMAIL", "team@x.com"):
        executed = _run(process_signal(session, sig))

    assert "create_scheduling_request" in executed
    assert "email_sales_team" in executed
    reqs = session.exec(select(SchedulingRequest)).all()
    assert len(reqs) == 1
    assert reqs[0].contact_id == contact.id
    assert reqs[0].signal_event_id == sig.id


def test_process_signal_email_sales_team_no_team_email(session: Session) -> None:
    """When TEAM_NOTIFICATION_EMAIL is empty, email_sales_team returns silently."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="scheduling_requested")
    with patch.object(trigger_service.settings, "TEAM_NOTIFICATION_EMAIL", ""):
        executed = _run(process_signal(session, sig))
    assert "email_sales_team" in executed


def test_process_signal_email_sales_team_missing_contact(session: Session) -> None:
    """email_sales_team early-returns when contact is missing."""
    sig = _make_signal(session, uuid.uuid4(), signal_type="scheduling_requested")
    with patch.object(trigger_service.settings, "TEAM_NOTIFICATION_EMAIL", "team@x.com"):
        executed = _run(process_signal(session, sig))
    assert "email_sales_team" in executed


def test_process_signal_voice_positive_interest_sends_resource(
    session: Session,
) -> None:
    """voice_positive_interest sends resource email."""
    contact = _make_contact(session, first_name=None)
    sig = _make_signal(
        session, contact.id, signal_type="voice_positive_interest", channel="voice"
    )
    executed = _run(process_signal(session, sig))
    assert executed == ["send_resource_email"]


def test_process_signal_resolves_workspace_email_adapter(session: Session) -> None:
    """Email trigger actions resolve the workspace-selected email provider."""
    workspace_id = "ws-provider-selected"
    contact = _make_contact(session, workspace_id=workspace_id)
    campaign = _make_campaign(session, workspace_id=workspace_id)
    sig = _make_signal(
        session,
        contact.id,
        signal_type="voice_positive_interest",
        channel="voice",
        campaign_id=campaign.id,
    )
    adapter = AsyncMock()
    adapter.send_email = AsyncMock(return_value={"status_code": 250})

    with patch.object(
        trigger_service,
        "resolve_email_adapter",
        return_value=adapter,
    ) as resolver:
        executed = _run(process_signal(session, sig))

    assert executed == ["send_resource_email"]
    resolver.assert_called_once_with(
        session,
        workspace_id,
        default_factory=trigger_service.SendGridAdapter,
    )
    adapter.send_email.assert_awaited_once()


def test_process_signal_demo_email_uses_outbox_intent_and_skips_duplicate(
    session: Session,
) -> None:
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="email_positive_reply")
    adapter = _CapturingEmailAdapter(session)

    with patch.object(trigger_service, "resolve_email_adapter", return_value=adapter):
        first = _run(process_signal(session, sig))
        second = _run(process_signal(session, sig))

    expected_key = f"signal:{sig.id}:action:send_demo_email"
    outbox = session.exec(select(OutboxEvent)).all()
    assert "send_demo_email" in first
    assert "send_demo_email" in second
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["idempotency_key"] == expected_key
    assert [event.idempotency_key for event in outbox] == [expected_key]
    assert outbox[0].published_at is not None


def test_process_signal_sales_email_uses_outbox_intent_and_skips_duplicate(
    session: Session,
) -> None:
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="scheduling_requested")
    adapter = _CapturingEmailAdapter(session)

    with (
        patch.object(trigger_service, "resolve_email_adapter", return_value=adapter),
        patch.object(
            trigger_service,
            "resolve_team_notification_email",
            return_value="team@example.com",
        ),
    ):
        first = _run(process_signal(session, sig))
        second = _run(process_signal(session, sig))

    expected_key = f"signal:{sig.id}:action:email_sales_team"
    outbox = session.exec(select(OutboxEvent)).all()
    assert "email_sales_team" in first
    assert "email_sales_team" in second
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["to"] == "team@example.com"
    assert adapter.sent[0]["idempotency_key"] == expected_key
    assert [event.idempotency_key for event in outbox] == [expected_key]
    assert outbox[0].published_at is not None


def test_process_signal_resource_email_uses_outbox_intent_and_skips_duplicate(
    session: Session,
) -> None:
    contact = _make_contact(session)
    sig = _make_signal(
        session, contact.id, signal_type="voice_positive_interest", channel="voice"
    )
    adapter = _CapturingEmailAdapter(session)

    with patch.object(trigger_service, "resolve_email_adapter", return_value=adapter):
        first = _run(process_signal(session, sig))
        second = _run(process_signal(session, sig))

    expected_key = f"signal:{sig.id}:action:send_resource_email"
    outbox = session.exec(select(OutboxEvent)).all()
    assert first == ["send_resource_email"]
    assert second == ["send_resource_email"]
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["idempotency_key"] == expected_key
    assert [event.idempotency_key for event in outbox] == [expected_key]
    assert outbox[0].published_at is not None


def test_process_signal_resource_email_does_not_retry_unpublished_intent(
    session: Session,
) -> None:
    contact = _make_contact(session)
    sig = _make_signal(
        session, contact.id, signal_type="voice_positive_interest", channel="voice"
    )
    session.add(
        OutboxEvent(
            aggregate_id=sig.id,
            aggregate_type="signal",
            event_type="trigger.resource_email_send_requested",
            event_data={"to": contact.email},
            idempotency_key=f"signal:{sig.id}:action:send_resource_email",
        )
    )
    session.commit()
    adapter = _CapturingEmailAdapter(session)

    with patch.object(trigger_service, "resolve_email_adapter", return_value=adapter):
        executed = _run(process_signal(session, sig))

    outbox = session.exec(select(OutboxEvent)).all()
    assert executed == []
    assert adapter.sent == []
    assert len(outbox) == 1
    assert outbox[0].published_at is None


def test_process_signal_resource_email_rejection_leaves_intent_unpublished(
    session: Session,
) -> None:
    contact = _make_contact(session)
    sig = _make_signal(
        session, contact.id, signal_type="voice_positive_interest", channel="voice"
    )
    adapter = AsyncMock()
    adapter.send_email = AsyncMock(return_value={"status_code": 500, "message_id": ""})

    with patch.object(trigger_service, "resolve_email_adapter", return_value=adapter):
        executed = _run(process_signal(session, sig))

    outbox = session.exec(select(OutboxEvent)).all()
    assert executed == []
    adapter.send_email.assert_awaited_once()
    assert len(outbox) == 1
    assert outbox[0].published_at is None


def test_process_signal_send_resource_missing_contact(session: Session) -> None:
    """send_resource_email returns silently when contact missing."""
    sig = _make_signal(
        session, uuid.uuid4(), signal_type="voice_positive_interest", channel="voice"
    )
    executed = _run(process_signal(session, sig))
    assert executed == ["send_resource_email"]


def test_process_signal_action_exception_logged_not_raised(
    session: Session,
) -> None:
    """An adapter that raises does not abort other actions."""
    contact = _make_contact(session)
    sig = _make_signal(session, contact.id, signal_type="email_positive_reply")
    _make_voice_script(session, sig.campaign_id, active=True)

    with patch.object(trigger_service, "SendGridAdapter") as adapter_cls:
        adapter_cls.return_value.send_email = AsyncMock(side_effect=RuntimeError("boom"))
        executed = _run(process_signal(session, sig))

    assert "queue_followup_call" in executed
    assert "send_demo_email" not in executed


# ---------- get_trigger_rules / set_trigger_enabled ----------


def test_get_trigger_rules_returns_all_defaults() -> None:
    """Listing rules covers every key in DEFAULT_RULES."""
    rules = get_trigger_rules()
    types = {r["signal_type"] for r in rules}
    assert types == set(DEFAULT_RULES.keys())
    for rule in rules:
        assert "actions" in rule
        assert "enabled" in rule


def test_set_trigger_enabled_returns_true_for_known_type() -> None:
    """Toggling a known type returns True and updates state."""
    assert set_trigger_enabled("email_positive_reply", False) is True
    assert trigger_service._trigger_enabled["email_positive_reply"] is False
    set_trigger_enabled("email_positive_reply", True)


def test_set_trigger_enabled_returns_false_for_unknown() -> None:
    """Unknown signal types return False."""
    assert set_trigger_enabled("nope", False) is False
