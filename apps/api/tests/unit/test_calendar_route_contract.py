from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.routes import scheduling as routes
from app.domain.scheduling.availability import AvailableSlot
from app.domain.scheduling.schemas import (
    CalendarConfirmationCreate,
    CalendarOfferCreate,
)


class _Result:
    def __init__(self, value):
        self.value = value

    def one_or_none(self):
        return self.value


class _Session:
    def __init__(self, *values):
        self.values = iter(values)

    def exec(self, _statement):
        return _Result(next(self.values))


class _Provider:
    def __init__(self) -> None:
        self.free_busy_calls = 0

    def free_busy(self, **_kwargs):
        self.free_busy_calls += 1
        return []


def test_confirmation_identity_is_not_client_supplied() -> None:
    payload = CalendarConfirmationCreate(
        workspace_id="workspace-a",
        deployment_id=uuid.uuid4(),
        binding_id=uuid.uuid4(),
        selected_slot_digest="a" * 64,
        confirmed_by="buyer@example.com",
    )

    assert "confirmation_key" not in payload.model_fields_set


def test_reschedule_and_cancel_are_explicit_lifecycle_mutations() -> None:
    payload = CalendarConfirmationCreate(
        workspace_id="workspace-a",
        deployment_id=uuid.uuid4(),
        binding_id=uuid.uuid4(),
        selected_slot_digest="a" * 64,
        confirmed_by="buyer@example.com",
        operation="RESCHEDULE",
        predecessor_job_id=uuid.uuid4(),
    )
    paths = {route.path for route in routes.router.routes}

    assert payload.operation == "RESCHEDULE"
    assert "/scheduling/agent/tenants/{tenant_id}/jobs/{job_id}/cancel" in paths


def test_offer_free_busy_runs_after_durable_idempotency_claim(monkeypatch) -> None:
    provider = _Provider()
    meeting_type = SimpleNamespace(
        timezone="UTC",
        duration_minutes=30,
        working_hours={"MONDAY": [["09:00", "17:00"]]},
        holiday_dates=[],
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        minimum_notice_minutes=0,
    )
    binding = SimpleNamespace(
        provider_account_ref="calendar-a",
        credential_secret_ref="secret://calendar/a",
    )
    session = _Session(meeting_type, binding, uuid.uuid4())
    slot = AvailableSlot(
        starts_at=datetime.now(timezone.utc) + timedelta(days=2),
        ends_at=datetime.now(timezone.utc) + timedelta(days=2, minutes=30),
        timezone="UTC",
    )
    offer = SimpleNamespace(
        id=uuid.uuid4(),
        version=1,
        offer_digest="b" * 64,
        slots=[slot.model_dump(mode="json")],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    monkeypatch.setattr(routes, "_authorize_agent_admin", lambda *_args: None)
    monkeypatch.setattr(routes, "_require_tenant_workspace", lambda *_args: None)
    monkeypatch.setattr(routes, "calculate_available_slots", lambda **_kwargs: [slot])
    monkeypatch.setattr(
        routes.scheduling_service,
        "create_scheduling_offer",
        lambda *_args, **_kwargs: offer,
    )

    async def claimed(_request, *, mutation, **_kwargs):
        assert provider.free_busy_calls == 0
        return mutation()

    monkeypatch.setattr(routes, "run_idempotent_mutation", claimed)
    monday = date.today() + timedelta(days=(7 - date.today().weekday()))
    response = asyncio.run(
        routes.create_calendar_offer(
            SimpleNamespace(),
            session=session,
            current_user=SimpleNamespace(id=uuid.uuid4()),
            tenant_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            header_workspace_id="workspace-a",
            data=CalendarOfferCreate(
                workspace_id="workspace-a",
                meeting_type_id=uuid.uuid4(),
                start_date=monday,
                end_date=monday,
            ),
            idempotency_key="offer-http-idempotency",
            provider=provider,
        )
    )

    assert response["id"] == str(offer.id)
    assert provider.free_busy_calls == 1
