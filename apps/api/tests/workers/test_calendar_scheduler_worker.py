from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import SQLModel, func, select

from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentType,
    AgentUsageLedger,
    AgentUsageState,
)
from app.domain.scheduling.models import (
    CalendarBookingJob,
    CalendarBookingReceipt,
    CalendarMeetingType,
    CalendarProviderBinding,
    SchedulingConfirmation,
    SchedulingOffer,
    SchedulingRequest,
)
from app.domain.scheduling.providers import (
    CalendarBookingCommand,
    CalendarProviderReceipt,
)
from app.domain.scheduling.service import slot_digest
from app.domain.scheduling.worker import (
    reconcile_unknown_booking,
    recover_expired_booking_leases,
    run_calendar_booking_batch,
)
from app.domain.tenants.models import ProductCode, TenantOperationalControl
from tests.domain.test_proposal_agent import _context, _session


class CalendarAdapter:
    def __init__(self, *, lose_response: bool = False) -> None:
        self.calls = 0
        self.lose_response = lose_response
        self.receipts: dict[str, CalendarProviderReceipt] = {}

    def free_busy(self, **_kwargs):
        return []

    def create_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        self.calls += 1
        receipt = CalendarProviderReceipt(
            command_key=command.command_key,
            provider_event_id=f"event-{command.command_key}",
            provider_receipt_id=f"receipt-{command.command_key}",
            starts_at=command.starts_at,
            ends_at=command.ends_at,
        )
        self.receipts[command.command_key] = receipt
        if self.lose_response:
            raise TimeoutError("provider accepted the event but response was lost")
        return receipt

    def lookup_event(self, command_key: str) -> CalendarProviderReceipt | None:
        return self.receipts.get(command_key)


def test_booking_success_finalizes_one_meeting_and_receipt() -> None:
    with _session() as session:
        job = _calendar_job(session)
        adapter = CalendarAdapter()

        assert run_calendar_booking_batch(session, provider=adapter) == 1
        session.refresh(job)

        assert job.status == "COMPLETED"
        assert adapter.calls == 1
        assert session.exec(select(func.count(CalendarBookingReceipt.id))).one() == 1
        assert (
            session.exec(select(AgentUsageLedger)).one().state
            == AgentUsageState.FINALIZED
        )


def test_accepted_then_timeout_is_unknown_and_never_automatically_retried() -> None:
    with _session() as session:
        job = _calendar_job(session)
        adapter = CalendarAdapter(lose_response=True)

        run_calendar_booking_batch(session, provider=adapter)
        run_calendar_booking_batch(session, provider=adapter)
        session.refresh(job)

        assert job.status == "UNKNOWN_PROVIDER_OUTCOME"
        assert adapter.calls == 1
        assert (
            session.exec(select(AgentUsageLedger)).one().state
            == AgentUsageState.UNKNOWN
        )

        reconciled = reconcile_unknown_booking(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            provider=adapter,
            actor_id=uuid.uuid4(),
            actor_role="tenant_owner",
            capabilities={"agents.admin.manage"},
        )
        assert reconciled.status == "COMPLETED"


def test_final_busy_recheck_requires_new_confirmation_without_provider_call() -> None:
    with _session() as session:
        job = _calendar_job(session)

        class BusyAdapter(CalendarAdapter):
            def free_busy(self, **_kwargs):
                confirmation = session.get(SchedulingConfirmation, job.confirmation_id)
                offer = session.get(SchedulingOffer, confirmation.offer_id)
                slot = offer.slots[0]
                from app.domain.scheduling.availability import BusyInterval

                return [
                    BusyInterval(
                        starts_at=datetime.fromisoformat(slot["starts_at"]),
                        ends_at=datetime.fromisoformat(slot["ends_at"]),
                    )
                ]

        adapter = BusyAdapter()
        run_calendar_booking_batch(session, provider=adapter)
        session.refresh(job)
        assert job.status == "INPUT_REQUIRED"
        assert adapter.calls == 0


def test_signal_loop_kill_switch_blocks_booking_claim() -> None:
    with _session() as session:
        job = _calendar_job(session)
        session.add(
            TenantOperationalControl(
                tenant_id=job.tenant_id,
                product_code=ProductCode.SIGNAL_LOOP,
                paused=True,
                reason="incident",
                changed_by=uuid.uuid4(),
            )
        )
        session.commit()
        adapter = CalendarAdapter()
        assert run_calendar_booking_batch(session, provider=adapter) == 0
        session.refresh(job)
        assert job.status == "PENDING"
        assert adapter.calls == 0


def test_lease_recovery_retries_only_before_provider_attempt() -> None:
    with _session() as session:
        safe = _calendar_job(session)
        attempted = _calendar_job(session)
        now = datetime.now(timezone.utc)
        for job in (safe, attempted):
            job.status = "IN_PROGRESS"
            job.lease_token = uuid.uuid4()
            job.lease_expires_at = now - timedelta(seconds=1)
        attempted.provider_attempted_at = now - timedelta(minutes=1)
        session.add_all([safe, attempted])
        session.commit()

        assert recover_expired_booking_leases(session, now=now) == 2
        session.commit()
        session.refresh(safe)
        session.refresh(attempted)
        assert safe.status == "RETRY_SCHEDULED"
        assert attempted.status == "UNKNOWN_PROVIDER_OUTCOME"


def _calendar_job(session) -> CalendarBookingJob:
    engine = session.get_bind()
    SQLModel.metadata.create_all(
        engine,
        tables=[
            TenantOperationalControl.__table__,
            CalendarMeetingType.__table__,
            CalendarProviderBinding.__table__,
            SchedulingOffer.__table__,
            SchedulingConfirmation.__table__,
            CalendarBookingJob.__table__,
            CalendarBookingReceipt.__table__,
            SchedulingRequest.__table__,
        ],
    )
    proposal_deployment, proposal_job = _context(session)
    suffix = uuid.uuid4().hex[:8]
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.CALENDAR_SCHEDULER,
        catalog_version=10_000_000 + int(suffix[:5], 16),
        display_name="Calendar Scheduler Agent",
        sellable_outcome="Confirm meetings",
        default_capacity_metric="confirmed_meeting",
        default_capacity_amount=100,
        configuration_schema_version="calendar.v1",
    )
    session.add(catalog)
    session.flush()
    deployment = AgentDeployment(
        tenant_id=proposal_deployment.tenant_id,
        installation_id=proposal_deployment.installation_id,
        workspace_id=proposal_deployment.workspace_id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.CALENDAR_SCHEDULER,
        name=f"Calendar {suffix}",
        status=AgentDeploymentStatus.ACTIVE,
        configuration={},
        configuration_digest="e" * 64,
    )
    meeting_type = CalendarMeetingType(
        tenant_id=proposal_deployment.tenant_id,
        workspace_id=proposal_deployment.workspace_id,
        name=f"Discovery {suffix}",
        duration_minutes=30,
        timezone="UTC",
        working_hours={"MONDAY": [["09:00", "17:00"]]},
    )
    binding = CalendarProviderBinding(
        tenant_id=proposal_deployment.tenant_id,
        workspace_id=proposal_deployment.workspace_id,
        provider="CALENDLY",
        provider_account_ref=f"account-{suffix}",
        credential_secret_ref=f"secret://calendar/{suffix}",
        capabilities=["free_busy.read", "event.create", "event.lookup"],
    )
    session.add_all([deployment, meeting_type, binding])
    session.flush()
    starts = datetime.now(timezone.utc) + timedelta(days=2)
    slot = {
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(minutes=30)).isoformat(),
        "timezone": "UTC",
    }
    offer = SchedulingOffer(
        tenant_id=deployment.tenant_id,
        workspace_id=deployment.workspace_id,
        scheduling_request_id=proposal_job.id,
        meeting_type_id=meeting_type.id,
        version=1,
        offer_digest=uuid.uuid4().hex * 2,
        slots=[slot],
        expires_at=starts - timedelta(hours=1),
        status="CONFIRMED",
    )
    session.add(offer)
    session.flush()
    confirmation = SchedulingConfirmation(
        tenant_id=deployment.tenant_id,
        workspace_id=deployment.workspace_id,
        offer_id=offer.id,
        selected_slot_digest=slot_digest(slot),
        confirmed_by="buyer@example.com",
        confirmation_key=f"confirm-{suffix}",
    )
    session.add(confirmation)
    session.flush()
    job = CalendarBookingJob(
        tenant_id=deployment.tenant_id,
        workspace_id=deployment.workspace_id,
        deployment_id=deployment.id,
        binding_id=binding.id,
        confirmation_id=confirmation.id,
        command_key=f"calendar:{confirmation.id}",
    )
    session.add(job)
    session.commit()
    return job
