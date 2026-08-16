# ruff: noqa: E402, I001 -- preload legacy tables before lifecycle extensions.
from __future__ import annotations

import importlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Table, Uuid
from sqlmodel import SQLModel, func, select

_legacy_scheduling = importlib.import_module("app.domain.signals.scheduling")

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
    enqueue_calendar_lifecycle_job,
    reconcile_unknown_booking,
    recover_expired_booking_leases,
    run_calendar_booking_batch,
)
from app.domain.tenants.models import ProductCode, TenantOperationalControl
from tests.domain.test_proposal_agent import _context, _session


class CalendarAdapter:
    def __init__(
        self,
        *,
        lose_response: bool = False,
        lose_operations: set[str] | None = None,
    ) -> None:
        self.calls = 0
        self.operations: list[str] = []
        self.lose_response = lose_response
        self.lose_operations = lose_operations or set()
        self.receipts: dict[str, CalendarProviderReceipt] = {}

    def free_busy(self, **_kwargs):
        return []

    def create_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        self.calls += 1
        self.operations.append("BOOK")
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

    def lookup_event(
        self, command_key: str, _credential_secret_ref: str
    ) -> CalendarProviderReceipt | None:
        return self.receipts.get(command_key)

    def reschedule_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt:
        self.operations.append("RESCHEDULE")
        return self._receipt(command, operation="RESCHEDULE")

    def cancel_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        self.operations.append("CANCEL")
        return self._receipt(command, operation="CANCEL")

    def _receipt(
        self, command: CalendarBookingCommand, *, operation: str
    ) -> CalendarProviderReceipt:
        self.calls += 1
        receipt = CalendarProviderReceipt(
            command_key=command.command_key,
            provider_event_id=command.provider_event_id
            or f"event-{command.command_key}",
            provider_receipt_id=f"receipt-{command.command_key}",
            starts_at=command.starts_at,
            ends_at=command.ends_at,
        )
        self.receipts[command.command_key] = receipt
        if operation in self.lose_operations:
            raise TimeoutError(f"provider accepted {operation} but response was lost")
        return receipt


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


def test_book_reschedule_cancel_use_immutable_per_operation_capacity() -> (
    None
):
    with _session() as session:
        book = _calendar_job(session)
        adapter = CalendarAdapter()

        assert run_calendar_booking_batch(session, provider=adapter) == 1
        session.refresh(book)
        assert book.provider_event_id is not None

        reschedule = enqueue_calendar_lifecycle_job(
            session,
            tenant_id=book.tenant_id,
            workspace_id=book.workspace_id,
            deployment_id=book.deployment_id,
            binding_id=book.binding_id,
            confirmation_id=book.confirmation_id,
            operation="RESCHEDULE",
            predecessor_job_id=book.id,
        )
        session.commit()
        assert run_calendar_booking_batch(session, provider=adapter) == 1
        session.refresh(reschedule)

        cancel = enqueue_calendar_lifecycle_job(
            session,
            tenant_id=book.tenant_id,
            workspace_id=book.workspace_id,
            deployment_id=book.deployment_id,
            binding_id=book.binding_id,
            confirmation_id=book.confirmation_id,
            operation="CANCEL",
            predecessor_job_id=reschedule.id,
        )
        session.commit()
        assert run_calendar_booking_batch(session, provider=adapter) == 1
        session.refresh(cancel)

        assert [book.generation, reschedule.generation, cancel.generation] == [1, 2, 3]
        assert adapter.operations == ["BOOK", "RESCHEDULE", "CANCEL"]
        receipts = session.exec(
            select(CalendarBookingReceipt).order_by(CalendarBookingReceipt.generation)
        ).all()
        assert [receipt.operation for receipt in receipts] == [
            "BOOK",
            "RESCHEDULE",
            "CANCEL",
        ]
        assert receipts[1].previous_provider_event_id == book.provider_event_id
        assert receipts[2].previous_provider_event_id == reschedule.provider_event_id
        assert session.exec(select(func.count(AgentUsageLedger.id))).one() == 3


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


def test_receipt_absence_with_operator_evidence_requeues_and_releases_capacity() -> (
    None
):
    with _session() as session:
        job = _calendar_job(session)

        class MissingReceiptAdapter(CalendarAdapter):
            def create_event(self, _command):
                self.calls += 1
                raise TimeoutError("ambiguous connection close")

        adapter = MissingReceiptAdapter()
        run_calendar_booking_batch(session, provider=adapter)
        session.refresh(job)
        assert job.status == "UNKNOWN_PROVIDER_OUTCOME"

        reconciled = reconcile_unknown_booking(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            provider=adapter,
            actor_id=uuid.uuid4(),
            actor_role="tenant_owner",
            capabilities={"agents.admin.manage"},
            provider_accepted=False,
            provider_evidence_id="calendly-lookup-none-20260816",
            reason="Calendly lookup proved no event",
        )
        session.commit()
        assert reconciled.status == "PENDING"
        assert (
            session.exec(select(AgentUsageLedger)).one().state
            == AgentUsageState.RELEASED
        )


def test_negative_book_reconciliation_retries_with_a_fresh_reservation() -> None:
    with _session() as session:
        job = _calendar_job(session)

        class MissingReceiptAdapter(CalendarAdapter):
            def create_event(self, _command):
                self.calls += 1
                raise TimeoutError("ambiguous connection close")

        missing = MissingReceiptAdapter()
        run_calendar_booking_batch(session, provider=missing)
        reconcile_unknown_booking(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            provider=missing,
            actor_id=uuid.uuid4(),
            actor_role="tenant_owner",
            capabilities={"agents.admin.manage"},
            provider_accepted=False,
            provider_evidence_id="lookup-none-first-attempt",
        )
        session.commit()

        assert run_calendar_booking_batch(session, provider=CalendarAdapter()) == 1
        session.refresh(job)
        reservations = session.exec(
            select(AgentUsageLedger).order_by(AgentUsageLedger.created_at)
        ).all()
        assert job.status == "COMPLETED"
        assert [item.state for item in reservations] == [
            AgentUsageState.RELEASED,
            AgentUsageState.FINALIZED,
        ]
        assert len({item.idempotency_key for item in reservations}) == 2


def test_accepted_timeout_reconciliation_preserves_stable_event_lifecycle() -> None:
    with _session() as session:
        book = _calendar_job(session)
        adapter = CalendarAdapter()
        run_calendar_booking_batch(session, provider=adapter)
        session.refresh(book)
        stable_event_id = book.provider_event_id

        for operation in ("RESCHEDULE", "CANCEL"):
            successor = enqueue_calendar_lifecycle_job(
                session,
                tenant_id=book.tenant_id,
                workspace_id=book.workspace_id,
                deployment_id=book.deployment_id,
                binding_id=book.binding_id,
                confirmation_id=book.confirmation_id,
                operation=operation,
                predecessor_job_id=book.id,
            )
            session.commit()
            adapter.lose_operations = {operation}
            run_calendar_booking_batch(session, provider=adapter)
            session.refresh(successor)
            assert successor.status == "UNKNOWN_PROVIDER_OUTCOME"

            reconcile_unknown_booking(
                session,
                tenant_id=successor.tenant_id,
                workspace_id=successor.workspace_id,
                job_id=successor.id,
                provider=adapter,
                actor_id=uuid.uuid4(),
                actor_role="tenant_owner",
                capabilities={"agents.admin.manage"},
            )
            session.commit()
            session.refresh(successor)
            receipt = session.exec(
                select(CalendarBookingReceipt).where(
                    CalendarBookingReceipt.confirmation_id == successor.confirmation_id,
                    CalendarBookingReceipt.operation == operation,
                    CalendarBookingReceipt.generation == successor.generation,
                )
            ).one()
            assert successor.provider_event_id == stable_event_id
            assert receipt.provider_event_id == stable_event_id
            assert receipt.previous_provider_event_id == stable_event_id
            book = successor


def test_reschedule_requires_update_capability_before_provider_dispatch() -> None:
    with _session() as session:
        book = _calendar_job(session)
        adapter = CalendarAdapter()
        run_calendar_booking_batch(session, provider=adapter)
        session.refresh(book)
        binding = session.get(CalendarProviderBinding, book.binding_id)
        binding.capabilities = ["free_busy.read", "event.create", "event.lookup"]
        session.add(binding)
        reschedule = enqueue_calendar_lifecycle_job(
            session,
            tenant_id=book.tenant_id,
            workspace_id=book.workspace_id,
            deployment_id=book.deployment_id,
            binding_id=book.binding_id,
            confirmation_id=book.confirmation_id,
            operation="RESCHEDULE",
            predecessor_job_id=book.id,
        )
        session.commit()

        run_calendar_booking_batch(session, provider=adapter)
        session.refresh(reschedule)
        assert reschedule.status == "RETRY_SCHEDULED"
        assert reschedule.provider_attempted_at is None
        assert adapter.operations == ["BOOK"]


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


def test_kill_switch_activated_after_free_busy_blocks_provider_dispatch() -> None:
    with _session() as session:
        job = _calendar_job(session)

        class PausingAdapter(CalendarAdapter):
            def free_busy(self, **_kwargs):
                session.add(
                    TenantOperationalControl(
                        tenant_id=job.tenant_id,
                        product_code=ProductCode.SIGNAL_LOOP,
                        paused=True,
                        reason="incident during claim",
                        changed_by=uuid.uuid4(),
                    )
                )
                session.commit()
                return []

        adapter = PausingAdapter()
        assert run_calendar_booking_batch(session, provider=adapter) == 1
        session.refresh(job)
        assert job.status == "RETRY_SCHEDULED"
        assert job.provider_attempted_at is None
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
    if "user" not in SQLModel.metadata.tables:
        Table(
            "user",
            SQLModel.metadata,
            Column("id", Uuid(), primary_key=True),
        )
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
        capabilities=[
            "free_busy.read",
            "event.create",
            "event.update",
            "event.cancel",
            "event.lookup",
        ],
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
