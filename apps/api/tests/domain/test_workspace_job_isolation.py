import uuid
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy import UniqueConstraint, create_engine
from sqlmodel import Session

from app.api.routes import voice, webhooks
from app.domain.outreach.action_queue_service import (
    list_pending_actions,
    update_action_status,
)
from app.domain.sequences.models import SendRequest
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain_models import (
    ActionQueue,
    Contact,
    NotificationProvider,
    OutboxEvent,
    ProviderEventLog,
)


def _unique_columns(model: type) -> set[tuple[str, ...]]:
    table = cast(Any, model).__table__
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_send_request_retry_and_provider_ids_are_workspace_scoped() -> None:
    send_request_table = cast(Any, SendRequest).__table__
    workspace_column = send_request_table.columns.get("workspace_id")

    assert workspace_column is not None, "SendRequest must store workspace ownership"
    assert workspace_column.nullable is False
    unique_columns = _unique_columns(SendRequest)
    assert ("workspace_id", "idempotency_key") in unique_columns
    assert ("workspace_id", "provider_message_id") in unique_columns
    assert ("idempotency_key",) not in unique_columns


def test_action_queue_stores_non_nullable_workspace_ownership() -> None:
    workspace_column = cast(Any, ActionQueue).__table__.columns.get("workspace_id")

    assert workspace_column is not None, "ActionQueue must store workspace ownership"
    assert workspace_column.nullable is False


def test_all_durable_dispatch_state_has_non_nullable_workspace_ownership() -> None:
    for model in (OutboxEvent, SignalEvent, SchedulingRequest):
        workspace_column = cast(Any, model).__table__.columns.get("workspace_id")
        assert workspace_column is not None, f"{model.__name__} must store workspace"
        assert workspace_column.nullable is False

    assert ("workspace_id", "idempotency_key") in _unique_columns(OutboxEvent)
    assert ("workspace_id", "source_event_id", "signal_type") in _unique_columns(
        SignalEvent
    )
    assert ("workspace_id", "signal_event_id") in _unique_columns(SchedulingRequest)


def test_contact_persists_channel_specific_consent() -> None:
    table = cast(Any, Contact).__table__
    assert table.columns["consent_email"].nullable is False
    assert table.columns["consent_voice"].nullable is False


def test_action_queue_list_and_update_are_workspace_scoped() -> None:
    engine = create_engine("sqlite://")
    cast(Any, ActionQueue).__table__.create(engine)
    action_a = ActionQueue(
        workspace_id="workspace-a",
        contact_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        action_type="send_email",
        channel="email",
    )
    action_b = ActionQueue(
        workspace_id="workspace-b",
        contact_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        action_type="send_email",
        channel="email",
    )
    with Session(engine) as session:
        session.add(action_a)
        session.add(action_b)
        session.commit()

        pending = list_pending_actions(
            session,
            workspace_id="workspace-a",
        )
        cross_workspace_update = update_action_status(
            session,
            workspace_id="workspace-b",
            action_id=action_a.id,
            status="completed",
        )

    assert [action.id for action in pending] == [action_a.id]
    assert cross_workspace_update is None


def test_same_send_identifiers_can_exist_in_two_workspaces() -> None:
    send_request_table = cast(Any, SendRequest).__table__
    if "workspace_id" not in send_request_table.columns:
        pytest.fail("SendRequest must store workspace ownership")

    engine = create_engine("sqlite://")
    send_request_table.create(engine)
    with Session(engine) as session:
        for workspace_id in ("workspace-a", "workspace-b"):
            session.add(
                SendRequest(
                    workspace_id=workspace_id,
                    contact_sequence_state_id=uuid.uuid4(),
                    step_order=1,
                    idempotency_key="same-retry-key",
                    provider_message_id="same-provider-message",
                )
            )
        session.commit()


def test_provider_event_replay_key_is_workspace_scoped() -> None:
    unique_columns = _unique_columns(ProviderEventLog)

    assert ("workspace_id", "provider", "provider_event_id") in unique_columns
    assert ("provider", "provider_event_id") not in unique_columns


def test_twilio_provider_event_id_can_repeat_in_two_workspaces() -> None:
    engine = create_engine("sqlite://")
    cast(Any, ProviderEventLog).__table__.create(engine)
    with Session(engine) as session:
        first = voice._record_twilio_provider_event(
            session,
            workspace_id="workspace-a",
            provider_event_id="same-provider-event",
            event_type="status",
            raw_payload={},
            normalized_event={},
        )
        session.flush()
        second = voice._record_twilio_provider_event(
            session,
            workspace_id="workspace-b",
            provider_event_id="same-provider-event",
            event_type="status",
            raw_payload={},
            normalized_event={},
        )

    assert first is True
    assert second is True


def test_sendgrid_provider_event_seen_is_workspace_scoped() -> None:
    engine = create_engine("sqlite://")
    cast(Any, ProviderEventLog).__table__.create(engine)
    with Session(engine) as session:
        session.add(
            ProviderEventLog(
                workspace_id="workspace-a",
                provider=NotificationProvider.sendgrid,
                provider_event_id="same-provider-event",
                event_type="delivered",
            )
        )
        session.commit()

        assert (
            webhooks._provider_event_seen(
                session,
                "workspace-b",
                "same-provider-event",
            )
            is False
        )


def test_sendgrid_event_rejects_missing_relational_ownership_chain() -> None:
    send_request = SendRequest(
        workspace_id="workspace-a",
        contact_sequence_state_id=uuid.uuid4(),
        step_order=1,
        idempotency_key="workspace-owned-event",
    )

    session = MagicMock()
    session.get.return_value = None

    with pytest.raises(ValueError, match="workspace ownership chain"):
        webhooks._workspace_for_send_request(session, send_request)
