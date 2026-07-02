from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.contacts.import_service import parse_csv, preview_rows, validate_rows
from app.domain.contacts.segment_service import estimate_segment, matches_rule
from app.domain.outreach.action_queue_service import (
    enqueue_action,
    list_pending_actions,
    update_action_status,
    write_dead_letter,
)
from app.domain_models import (
    ActionQueue,
    Campaign,
    Contact,
    DeadLetterEvent,
    SegmentOperator,
    SemanticError,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_campaign_and_contact(session: Session) -> tuple[Campaign, Contact]:
    owner_id = uuid.uuid4()
    campaign = Campaign(name="Campaign", workspace_id="ws-a", created_by=owner_id)
    session.add(campaign)
    session.flush()

    contact = Contact(
        workspace_id="ws-a",
        email="lead@example.com",
        first_name="Lead",
        company="Acme",
        phone="+15551234567",
    )
    session.add(contact)
    session.commit()
    session.refresh(campaign)
    session.refresh(contact)
    return campaign, contact


def test_parse_csv_handles_utf8_bom_and_rows() -> None:
    file_bytes = "\ufeffemail,firstName,company,timezone\nuser@example.com,Ada,Acme,UTC\n".encode("utf-8")
    headers, rows = parse_csv(file_bytes)

    assert headers == ["email", "firstName", "company", "timezone"]
    assert rows == [{"email": "user@example.com", "firstName": "Ada", "company": "Acme", "timezone": "UTC"}]


def test_validate_rows_returns_mapping_errors_when_required_fields_unmapped() -> None:
    headers = ["email", "firstName", "timezone"]
    valid_rows, errors = validate_rows(headers, rows=[{"email": "user@example.com"}])

    assert valid_rows == []
    assert len(errors) == 1
    assert errors[0].row_number == 0
    assert errors[0].column == "company"
    assert errors[0].semantic_error == SemanticError.recipient_invalid


def test_validate_rows_collects_row_level_required_field_errors() -> None:
    headers = ["email", "firstName", "company", "timezone"]
    rows = [
        {"email": "ok@example.com", "firstName": "Ada", "company": "Acme", "timezone": "UTC"},
        {"email": "", "firstName": "Casey", "company": "Acme", "timezone": "UTC"},
        {"email": "lead@example.com", "firstName": "", "company": "Acme", "timezone": "UTC"},
    ]

    valid_rows, errors = validate_rows(headers, rows)

    assert len(valid_rows) == 1
    assert valid_rows[0]["email"] == "ok@example.com"
    assert len(errors) == 2
    assert {(error.row_number, error.column) for error in errors} == {(2, "email"), (3, "firstName")}


def test_preview_rows_applies_limit_and_default_limit() -> None:
    rows = [{"n": index} for index in range(25)]

    assert preview_rows(rows, limit=3) == [{"n": 0}, {"n": 1}, {"n": 2}]
    assert len(preview_rows(rows)) == 20


def test_matches_rule_covers_supported_operators_and_unknown() -> None:
    assert matches_rule("Ada", SegmentOperator.equals, "Ada")
    assert not matches_rule("Ada", SegmentOperator.equals, "Casey")
    assert matches_rule("Ada Lovelace", SegmentOperator.contains, "lovelace")
    assert matches_rule("beta", SegmentOperator.in_list, "alpha, beta , gamma")
    assert matches_rule("whatsapp", SegmentOperator.starts_with, "what")
    assert not matches_rule("telegram", SegmentOperator.starts_with, "what")
    assert not matches_rule("anything", "unsupported-operator", "anything")  # type: ignore[arg-type]


def test_estimate_segment_requires_all_rules_to_match() -> None:
    rows = [
        {"email": "a@example.com", "company": "Acme"},
        {"email": "b@example.com", "company": "Beta"},
        {"email": "c@example.com", "company": "Acme"},
    ]
    rules = [
        {"field_name": "company", "operator": SegmentOperator.equals, "value": "Acme"},
        {"field_name": "email", "operator": SegmentOperator.contains, "value": "@example.com"},
    ]

    assert estimate_segment(rows, rules) == 2


def test_enqueue_action_persists_pending_action() -> None:
    with _session() as session:
        campaign, contact = _seed_campaign_and_contact(session)

        action = enqueue_action(
            session,
            contact_id=contact.id,
            campaign_id=campaign.id,
            action_type="send_email",
            channel="email",
            payload={"template": "t-1"},
        )

        assert action.status == "pending"
        saved = session.exec(select(ActionQueue).where(ActionQueue.id == action.id)).one()
        assert saved.payload == {"template": "t-1"}


def test_list_pending_actions_filters_by_status_and_respects_limit() -> None:
    with _session() as session:
        campaign, contact = _seed_campaign_and_contact(session)
        first = enqueue_action(
            session,
            contact_id=contact.id,
            campaign_id=campaign.id,
            action_type="send_email",
            channel="email",
            payload={"seq": 1},
        )
        second = enqueue_action(
            session,
            contact_id=contact.id,
            campaign_id=campaign.id,
            action_type="send_email",
            channel="email",
            payload={"seq": 2},
        )
        update_action_status(session, action_id=second.id, status="completed")

        pending = list_pending_actions(session, limit=1)

        assert len(pending) == 1
        assert pending[0].id == first.id


def test_update_action_status_returns_none_when_action_missing() -> None:
    with _session() as session:
        assert update_action_status(session, action_id=uuid.uuid4(), status="completed") is None


def test_update_action_status_sets_executed_at_for_completed() -> None:
    with _session() as session:
        campaign, contact = _seed_campaign_and_contact(session)
        action = enqueue_action(
            session,
            contact_id=contact.id,
            campaign_id=campaign.id,
            action_type="send_email",
            channel="email",
            payload={},
        )
        next_retry_at = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)

        completed = update_action_status(
            session,
            action_id=action.id,
            status="completed",
            next_retry_at=next_retry_at,
        )

        assert completed is not None
        assert completed.status == "completed"
        assert completed.executed_at is not None
        assert completed.next_retry_at == next_retry_at.replace(tzinfo=None)


def test_write_dead_letter_sets_status_and_creates_event() -> None:
    with _session() as session:
        campaign, contact = _seed_campaign_and_contact(session)
        action = enqueue_action(
            session,
            contact_id=contact.id,
            campaign_id=campaign.id,
            action_type="send_email",
            channel="email",
            payload={},
        )

        updated = write_dead_letter(
            session,
            action=action,
            failure_reason="provider timeout",
            workspace_id="ws-a",
        )

        assert updated.status == "dead_letter"
        assert updated.failure_reason == "provider timeout"
        assert updated.dead_lettered_at is not None

        dead_letter = session.exec(
            select(DeadLetterEvent).where(DeadLetterEvent.action_queue_id == action.id)
        ).one()
        assert dead_letter.workspace_id == "ws-a"
        assert dead_letter.failure_reason == "provider timeout"
        assert dead_letter.event_type == "dead_lettered"
