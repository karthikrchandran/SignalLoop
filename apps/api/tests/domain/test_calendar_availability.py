from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.domain.scheduling.availability import (
    AvailabilityPolicy,
    AvailableSlot,
    BusyInterval,
    CalendarAvailabilityError,
    calculate_available_slots,
)
from app.domain.scheduling.models import SchedulingOffer
from app.domain.scheduling.service import confirm_scheduling_offer, slot_digest
from app.domain.tenants.models import Tenant
from app.domain.workspaces.models import Workspace
from tests.domain.test_calendar_scheduler_models import _session


def test_invalid_iana_timezone_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        AvailabilityPolicy(
            timezone="India/Not-A-Zone",
            duration_minutes=30,
            working_hours={"MONDAY": [["09:00", "17:00"]]},
        )


def test_slots_respect_notice_holidays_buffers_conflicts_and_dst() -> None:
    policy = AvailabilityPolicy(
        timezone="America/New_York",
        duration_minutes=30,
        working_hours={"MONDAY": [["09:00", "12:00"]]},
        holiday_dates={date(2026, 3, 16)},
        buffer_before_minutes=15,
        buffer_after_minutes=15,
        minimum_notice_minutes=60,
        slot_interval_minutes=30,
    )
    now = datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)
    busy = [
        BusyInterval(
            starts_at=datetime(2026, 3, 9, 14, 30, tzinfo=timezone.utc),
            ends_at=datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc),
        )
    ]

    slots = calculate_available_slots(
        policy=policy,
        start_date=date(2026, 3, 9),
        end_date=date(2026, 3, 16),
        busy=busy,
        now=now,
        limit=20,
    )

    starts = {slot.starts_at.isoformat() for slot in slots}
    assert "2026-03-09T13:00:00+00:00" in starts  # 09:00 after DST switch
    assert "2026-03-09T14:00:00+00:00" not in starts  # provider busy + buffers
    assert all(slot.starts_at.date() != date(2026, 3, 16) for slot in slots)
    assert all(slot.starts_at >= now + timedelta(minutes=60) for slot in slots)


def test_end_date_before_start_and_unbounded_range_are_rejected() -> None:
    policy = AvailabilityPolicy(
        timezone="UTC",
        duration_minutes=30,
        working_hours={"MONDAY": [["09:00", "17:00"]]},
    )
    with pytest.raises(CalendarAvailabilityError):
        calculate_available_slots(
            policy=policy,
            start_date=date(2026, 8, 17),
            end_date=date(2026, 8, 16),
            busy=[],
        )
    with pytest.raises(CalendarAvailabilityError):
        calculate_available_slots(
            policy=policy,
            start_date=date(2026, 8, 17),
            end_date=date(2026, 10, 17),
            busy=[],
        )


def test_confirmation_is_exact_and_idempotent() -> None:
    with _session() as session:
        tenant = Tenant(key="confirm-offer", display_name="Confirm offer")
        workspace = Workspace(id="confirm-offer", name="Confirm offer")
        session.add_all([tenant, workspace])
        session.flush()
        starts_at = datetime.now(timezone.utc) + timedelta(days=1)
        slot = AvailableSlot(
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            timezone="UTC",
        ).model_dump(mode="json")
        offer = SchedulingOffer(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            scheduling_request_id=uuid.uuid4(),
            version=1,
            offer_digest="d" * 64,
            slots=[slot],
            expires_at=starts_at,
        )
        session.add(offer)
        session.commit()
        selected = slot_digest(slot)

        first = confirm_scheduling_offer(
            session,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            offer_id=offer.id,
            selected_slot_digest=selected,
            confirmed_by="buyer@example.com",
            confirmation_key="confirm-1",
        )
        replay = confirm_scheduling_offer(
            session,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            offer_id=offer.id,
            selected_slot_digest=selected,
            confirmed_by="buyer@example.com",
            confirmation_key="confirm-1",
        )
        assert replay.id == first.id
        assert session.exec(select(SchedulingOffer)).one().status == "CONFIRMED"
