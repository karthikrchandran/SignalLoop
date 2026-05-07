"""Unit tests for ``app.domain.signals.aggregation_service``."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.signals.aggregation_service import (
    get_campaign_signal_summary,
    get_contact_signals,
    get_latest_signal,
)
from app.domain.signals.models import SignalEvent


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """In-memory SQLite session per test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def _make_signal(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    channel: str = "email",
    signal_type: str = "email_positive_reply",
    created_at: datetime | None = None,
) -> SignalEvent:
    sig = SignalEvent(
        contact_id=contact_id,
        campaign_id=campaign_id,
        channel=channel,
        signal_type=signal_type,
    )
    if created_at is not None:
        sig.created_at = created_at
    session.add(sig)
    session.commit()
    session.refresh(sig)
    return sig


def test_get_contact_signals_returns_all_descending(session: Session) -> None:
    """All signals for the contact returned newest-first when no filters."""
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    base = datetime.now(timezone.utc)
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        created_at=base - timedelta(hours=2),
    )
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        created_at=base,
    )
    # noise: different contact
    _make_signal(
        session, contact_id=uuid.uuid4(), campaign_id=campaign_id,
    )

    results = get_contact_signals(session, contact_id)
    assert len(results) == 2
    assert results[0].created_at >= results[1].created_at


def test_get_contact_signals_filter_by_channel(session: Session) -> None:
    """Channel filter restricts to matching rows."""
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    _make_signal(session, contact_id=contact_id, campaign_id=campaign_id, channel="email")
    _make_signal(session, contact_id=contact_id, campaign_id=campaign_id, channel="voice")

    results = get_contact_signals(session, contact_id, channel="voice")
    assert len(results) == 1
    assert results[0].channel == "voice"


def test_get_contact_signals_filter_by_signal_type(session: Session) -> None:
    """Signal_type filter restricts results."""
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        signal_type="email_positive_reply",
    )
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        signal_type="scheduling_requested",
    )
    results = get_contact_signals(
        session, contact_id, signal_type="scheduling_requested"
    )
    assert len(results) == 1
    assert results[0].signal_type == "scheduling_requested"


def test_get_contact_signals_filter_by_since(session: Session) -> None:
    """Since filter excludes older rows."""
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        created_at=now - timedelta(days=2),
    )
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        created_at=now,
    )

    results = get_contact_signals(
        session, contact_id, since=now - timedelta(hours=1)
    )
    assert len(results) == 1


def test_get_contact_signals_combined_filters(session: Session) -> None:
    """All filters can be combined."""
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        channel="voice", signal_type="voice_positive_interest",
        created_at=now,
    )
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        channel="email", signal_type="email_positive_reply",
        created_at=now,
    )

    results = get_contact_signals(
        session, contact_id,
        channel="voice",
        signal_type="voice_positive_interest",
        since=now - timedelta(minutes=1),
    )
    assert len(results) == 1
    assert results[0].channel == "voice"


def test_get_contact_signals_empty_returns_empty_list(session: Session) -> None:
    """No matching signals -> empty list."""
    assert get_contact_signals(session, uuid.uuid4()) == []


def test_get_latest_signal_returns_newest(session: Session) -> None:
    """Latest signal is the most recent created_at."""
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    base = datetime.now(timezone.utc)
    _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        created_at=base - timedelta(hours=1),
    )
    newer = _make_signal(
        session, contact_id=contact_id, campaign_id=campaign_id,
        created_at=base,
    )
    result = get_latest_signal(session, contact_id)
    assert result is not None
    assert result.id == newer.id


def test_get_latest_signal_returns_none(session: Session) -> None:
    """No signals -> None."""
    assert get_latest_signal(session, uuid.uuid4()) is None


def test_get_campaign_signal_summary_groups_by_channel_and_type(session: Session) -> None:
    """Summary groups counts by channel then signal_type."""
    campaign_id = uuid.uuid4()
    contact = uuid.uuid4()
    _make_signal(session, contact_id=contact, campaign_id=campaign_id, channel="email", signal_type="reply")
    _make_signal(session, contact_id=contact, campaign_id=campaign_id, channel="email", signal_type="reply")
    _make_signal(session, contact_id=contact, campaign_id=campaign_id, channel="email", signal_type="open")
    _make_signal(session, contact_id=contact, campaign_id=campaign_id, channel="voice", signal_type="answered")
    # noise: different campaign
    _make_signal(session, contact_id=contact, campaign_id=uuid.uuid4(), channel="email", signal_type="reply")

    summary = get_campaign_signal_summary(session, campaign_id)
    assert summary == {
        "email": {"reply": 2, "open": 1},
        "voice": {"answered": 1},
    }


def test_get_campaign_signal_summary_empty(session: Session) -> None:
    """Empty campaign -> empty dict."""
    assert get_campaign_signal_summary(session, uuid.uuid4()) == {}
