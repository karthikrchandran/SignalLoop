from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.scheduling.models import (
    CalendarBookingReceipt,
    CalendarMeetingType,
    CalendarProviderBinding,
    SchedulingConfirmation,
    SchedulingOffer,
)
from app.domain.tenants.models import Tenant
from app.domain.workspaces.models import Workspace


def _session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            Workspace.__table__,
            CalendarMeetingType.__table__,
            CalendarProviderBinding.__table__,
            SchedulingOffer.__table__,
            SchedulingConfirmation.__table__,
            CalendarBookingReceipt.__table__,
        ],
    )
    return Session(engine)


def test_meeting_type_and_provider_binding_are_tenant_workspace_scoped() -> None:
    with _session() as session:
        tenant = Tenant(key="calendar-scope", display_name="Calendar scope")
        workspace = Workspace(id="calendar-scope", name="Calendar scope")
        session.add_all([tenant, workspace])
        session.commit()
        meeting_type = CalendarMeetingType(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            name="Discovery",
            duration_minutes=30,
            timezone="Asia/Kolkata",
            working_hours={"MONDAY": [["09:00", "17:00"]]},
            buffer_before_minutes=10,
            buffer_after_minutes=10,
            minimum_notice_minutes=120,
        )
        binding = CalendarProviderBinding(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            provider="CALENDLY",
            provider_account_ref="ara-calendar",
            credential_secret_ref="secret://calendar/ara",
            capabilities=["free_busy.read", "event.create", "event.lookup"],
        )
        session.add_all([meeting_type, binding])
        session.commit()
        assert meeting_type.workspace_id == binding.workspace_id


def test_offer_confirmation_and_receipt_identity_are_immutable_and_unique() -> None:
    with _session() as session:
        tenant = Tenant(key="calendar-offer", display_name="Calendar offer")
        workspace = Workspace(id="calendar-offer", name="Calendar offer")
        session.add_all([tenant, workspace])
        session.flush()
        now = datetime.now(timezone.utc)
        offer = SchedulingOffer(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            scheduling_request_id=uuid.uuid4(),
            version=1,
            offer_digest="a" * 64,
            slots=[
                {
                    "starts_at": now.isoformat(),
                    "ends_at": (now + timedelta(minutes=30)).isoformat(),
                }
            ],
            expires_at=now + timedelta(hours=1),
        )
        session.add(offer)
        session.flush()
        session.add(
            SchedulingConfirmation(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                offer_id=offer.id,
                selected_slot_digest="b" * 64,
                confirmed_by="contact@example.com",
                confirmation_key="confirm-once",
            )
        )
        session.flush()
        session.add(
            CalendarBookingReceipt(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                confirmation_id=session.exec(select(SchedulingConfirmation)).one().id,
                provider="CALENDLY",
                provider_event_id="event-1",
                provider_receipt_id="receipt-1",
                command_digest="c" * 64,
            )
        )
        session.commit()

        session.add(
            SchedulingConfirmation(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                offer_id=offer.id,
                selected_slot_digest="b" * 64,
                confirmed_by="other@example.com",
                confirmation_key="confirm-again",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
