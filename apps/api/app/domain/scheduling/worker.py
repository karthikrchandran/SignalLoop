"""Durable, lease-safe Calendar Scheduler Agent booking worker."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.commercial_agents.capacity import (
    finalize_capacity,
    mark_capacity_unknown,
    reconcile_unknown_capacity,
    reserve_capacity,
)
from app.domain.scheduling.availability import BusyInterval
from app.domain.scheduling.models import (
    CalendarBookingJob,
    CalendarBookingReceipt,
    CalendarMeetingType,
    CalendarProviderBinding,
    SchedulingConfirmation,
    SchedulingOffer,
    SchedulingRequest,
    SchedulingRequestStatus,
)
from app.domain.scheduling.providers import (
    CalendarBookingCommand,
    CalendarProvider,
    CalendarProviderReceipt,
)
from app.domain.scheduling.service import slot_digest
from app.domain.tenants.models import ProductCode, Tenant, TenantOperationalControl


class CalendarBookingError(ValueError):
    """A deterministic calendar booking state or ownership error."""


class CalendarSlotUnavailable(CalendarBookingError):
    """The selected slot became busy before provider invocation."""


CALENDAR_OPERATIONS = {"BOOK", "RESCHEDULE", "CANCEL"}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tenant_is_paused(session: Session, tenant_id: uuid.UUID) -> bool:
    return (
        session.exec(
            select(TenantOperationalControl.id).where(
                TenantOperationalControl.tenant_id == tenant_id,
                TenantOperationalControl.product_code == ProductCode.SIGNAL_LOOP.value,
                TenantOperationalControl.paused == True,  # noqa: E712
            )
        ).first()
        is not None
    )


def _claim(
    session: Session, *, now: datetime, lease_seconds: int = 300
) -> CalendarBookingJob | None:
    candidate = session.exec(
        select(CalendarBookingJob.id, CalendarBookingJob.tenant_id)
        .where(
            CalendarBookingJob.status.in_(["PENDING", "RETRY_SCHEDULED"]),
            CalendarBookingJob.available_at <= now,
        )
        .order_by(CalendarBookingJob.created_at, CalendarBookingJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    ).first()
    if candidate is None:
        return None
    candidate_id, tenant_id = candidate
    session.exec(
        select(Tenant.id).where(Tenant.id == tenant_id).with_for_update()
    ).one()
    if _tenant_is_paused(session, tenant_id):
        session.rollback()
        return None
    token = uuid.uuid4()
    result = session.exec(
        update(CalendarBookingJob)
        .where(
            CalendarBookingJob.id == candidate_id,
            CalendarBookingJob.status.in_(["PENDING", "RETRY_SCHEDULED"]),
            CalendarBookingJob.available_at <= now,
        )
        .values(
            status="IN_PROGRESS",
            attempt_count=CalendarBookingJob.attempt_count + 1,
            lease_token=token,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    return session.exec(
        select(CalendarBookingJob).where(
            CalendarBookingJob.id == candidate_id,
            CalendarBookingJob.lease_token == token,
        )
    ).one()


def _selected_slot(
    offer: SchedulingOffer, confirmation: SchedulingConfirmation
) -> dict[str, str]:
    matches = [
        slot
        for slot in offer.slots
        if slot_digest(slot) == confirmation.selected_slot_digest
    ]
    if len(matches) != 1:
        raise CalendarBookingError(
            "confirmation no longer matches exactly one offered slot"
        )
    return matches[0]


def _request_id_for_confirmation(
    session: Session, confirmation_id: uuid.UUID
) -> uuid.UUID:
    confirmation = session.get(SchedulingConfirmation, confirmation_id)
    offer = (
        None
        if confirmation is None
        else session.get(SchedulingOffer, confirmation.offer_id)
    )
    if offer is None:
        raise CalendarBookingError("owned scheduling confirmation is required")
    return offer.scheduling_request_id


def enqueue_calendar_lifecycle_job(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    deployment_id: uuid.UUID,
    binding_id: uuid.UUID,
    confirmation_id: uuid.UUID,
    operation: str,
    predecessor_job_id: uuid.UUID | None = None,
) -> CalendarBookingJob:
    """Append one immutable command generation to a calendar workflow."""

    normalized = operation.strip().upper()
    if normalized not in CALENDAR_OPERATIONS:
        raise CalendarBookingError("calendar lifecycle operation is invalid")
    generation = 1
    provider_event_id = None
    usage_reservation_id = None
    if normalized == "BOOK":
        if predecessor_job_id is not None:
            raise CalendarBookingError("BOOK cannot have a predecessor")
    else:
        predecessor = session.exec(
            select(CalendarBookingJob)
            .where(
                CalendarBookingJob.id == predecessor_job_id,
                CalendarBookingJob.tenant_id == tenant_id,
                CalendarBookingJob.workspace_id == workspace_id,
            )
            .with_for_update()
        ).one_or_none()
        if (
            predecessor is None
            or predecessor.status != "COMPLETED"
            or predecessor.operation == "CANCEL"
            or predecessor.provider_event_id is None
            or predecessor.usage_reservation_id is None
        ):
            raise CalendarBookingError("completed bookable predecessor is required")
        if (
            session.exec(
                select(CalendarBookingJob.id).where(
                    CalendarBookingJob.predecessor_job_id == predecessor.id
                )
            ).first()
            is not None
        ):
            raise CalendarBookingError("calendar lifecycle already has a successor")
        if _request_id_for_confirmation(
            session, predecessor.confirmation_id
        ) != _request_id_for_confirmation(session, confirmation_id):
            raise CalendarBookingError("lifecycle confirmations must own one request")
        generation = predecessor.generation + 1
        provider_event_id = predecessor.provider_event_id
        usage_reservation_id = predecessor.usage_reservation_id
    job = CalendarBookingJob(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        deployment_id=deployment_id,
        binding_id=binding_id,
        confirmation_id=confirmation_id,
        operation=normalized,
        generation=generation,
        provider_event_id=provider_event_id,
        predecessor_job_id=predecessor_job_id,
        usage_reservation_id=usage_reservation_id,
        command_key=f"calendar:{confirmation_id}:{normalized.lower()}:{generation}",
    )
    session.add(job)
    session.flush()
    return job


def _prepare_command(
    session: Session,
    *,
    job: CalendarBookingJob,
    provider: CalendarProvider,
    now: datetime,
) -> CalendarBookingCommand:
    confirmation = session.get(SchedulingConfirmation, job.confirmation_id)
    binding = session.get(CalendarProviderBinding, job.binding_id)
    if confirmation is None or binding is None or binding.status != "ACTIVE":
        raise CalendarBookingError(
            "active provider binding and confirmation are required"
        )
    if (
        confirmation.tenant_id != job.tenant_id
        or confirmation.workspace_id != job.workspace_id
        or binding.tenant_id != job.tenant_id
        or binding.workspace_id != job.workspace_id
    ):
        raise CalendarBookingError("calendar job references cross-tenant records")
    offer = session.get(SchedulingOffer, confirmation.offer_id)
    if (
        offer is None
        or offer.tenant_id != job.tenant_id
        or offer.workspace_id != job.workspace_id
    ):
        raise CalendarBookingError("owned scheduling offer is required")
    meeting_type = session.get(CalendarMeetingType, offer.meeting_type_id)
    if meeting_type is None or meeting_type.status != "ACTIVE":
        raise CalendarBookingError("active meeting type is required")
    if (
        meeting_type.tenant_id != job.tenant_id
        or meeting_type.workspace_id != job.workspace_id
    ):
        raise CalendarBookingError("meeting type is outside the calendar job scope")
    if job.operation == "CANCEL":
        predecessor = session.get(CalendarBookingJob, job.predecessor_job_id)
        prior = {} if predecessor is None else predecessor.command_envelope or {}
        if (
            predecessor is None
            or predecessor.provider_event_id != job.provider_event_id
        ):
            raise CalendarBookingError("owned cancellation predecessor is required")
        starts_at = _utc(
            datetime.fromisoformat(str(prior.get("starts_at")).replace("Z", "+00:00"))
        )
        ends_at = _utc(
            datetime.fromisoformat(str(prior.get("ends_at")).replace("Z", "+00:00"))
        )
    else:
        slot = _selected_slot(offer, confirmation)
        starts_at = _utc(datetime.fromisoformat(slot["starts_at"]))
        ends_at = _utc(datetime.fromisoformat(slot["ends_at"]))
        if starts_at <= now:
            raise CalendarSlotUnavailable("selected slot is no longer in the future")
        busy = provider.free_busy(
            provider_account_ref=binding.provider_account_ref,
            credential_secret_ref=binding.credential_secret_ref,
            start_date=starts_at.date(),
            end_date=ends_at.date(),
        )
        if any(_overlaps(starts_at, ends_at, interval) for interval in busy):
            raise CalendarSlotUnavailable("selected slot is no longer available")
    base = {
        "schema_version": "calendar-booking-command.v1",
        "command_key": job.command_key,
        "provider_account_ref": binding.provider_account_ref,
        "credential_secret_ref": binding.credential_secret_ref,
        "operation": job.operation,
        "provider_event_id": job.provider_event_id,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "attendee_email": confirmation.confirmed_by,
        "title": meeting_type.name,
        "timezone": meeting_type.timezone,
    }
    return CalendarBookingCommand(**base, command_digest=_digest(base))


def _overlaps(starts_at: datetime, ends_at: datetime, busy: BusyInterval) -> bool:
    return starts_at < _utc(busy.ends_at) and ends_at > _utc(busy.starts_at)


def _finalize(
    session: Session,
    *,
    job: CalendarBookingJob,
    receipt: CalendarProviderReceipt,
    now: datetime,
) -> None:
    token = job.lease_token
    if token is None or job.command_digest is None or job.usage_reservation_id is None:
        raise CalendarBookingError("owned booking lease and reservation are required")
    command = job.command_envelope or {}
    if (
        receipt.command_key != job.command_key
        or _utc(receipt.starts_at)
        != _utc(
            datetime.fromisoformat(str(command.get("starts_at")).replace("Z", "+00:00"))
        )
        or _utc(receipt.ends_at)
        != _utc(
            datetime.fromisoformat(str(command.get("ends_at")).replace("Z", "+00:00"))
        )
    ):
        raise CalendarBookingError("provider receipt does not match booking command")
    claimed = session.exec(
        update(CalendarBookingJob)
        .where(
            CalendarBookingJob.id == job.id,
            CalendarBookingJob.status == "IN_PROGRESS",
            CalendarBookingJob.lease_token == token,
            CalendarBookingJob.lease_expires_at >= now,
        )
        .values(
            status="COMPLETED",
            provider_event_id=receipt.provider_event_id,
            lease_token=None,
            lease_expires_at=None,
            last_error_code=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise CalendarBookingError("booking completion lease is no longer owned")
    if job.operation == "BOOK":
        finalize_capacity(
            session,
            reservation_id=job.usage_reservation_id,
            provider_receipt_id=receipt.provider_receipt_id,
            finalized_units=1,
            provider_units={"confirmed_meetings": 1},
            now=now,
        )
    session.add(
        CalendarBookingReceipt(
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            confirmation_id=job.confirmation_id,
            operation=job.operation,
            generation=job.generation,
            previous_provider_event_id=job.provider_event_id,
            provider=command.get("provider", "CALENDLY"),
            provider_event_id=receipt.provider_event_id,
            provider_receipt_id=receipt.provider_receipt_id,
            command_digest=job.command_digest,
            created_at=now,
        )
    )
    _sync_scheduling_request(session, job=job, receipt=receipt, now=now)
    _append_confirmation_audit(session, job=job, receipt=receipt)
    session.commit()


def _sync_scheduling_request(
    session: Session,
    *,
    job: CalendarBookingJob,
    receipt: CalendarProviderReceipt,
    now: datetime,
) -> None:
    confirmation = session.get(SchedulingConfirmation, job.confirmation_id)
    if confirmation is not None:
        offer = session.get(SchedulingOffer, confirmation.offer_id)
        if offer is not None:
            request = session.get(SchedulingRequest, offer.scheduling_request_id)
            if request is not None and request.workspace_id == job.workspace_id:
                request.status = (
                    SchedulingRequestStatus.cancelled
                    if job.operation == "CANCEL"
                    else SchedulingRequestStatus.booked
                )
                request.calendly_event_id = receipt.provider_event_id
                if job.operation != "CANCEL":
                    request.meeting_datetime = receipt.starts_at
                request.updated_at = now
                session.add(request)
    return None


def _append_confirmation_audit(
    session: Session,
    *,
    job: CalendarBookingJob,
    receipt: CalendarProviderReceipt,
) -> None:
    append_audit_event_to_session(
        session,
        event_name=f"calendar_scheduler.meeting.{job.operation.lower()}",
        workspace_id=job.workspace_id,
        resource_type="calendar_booking_job",
        resource_id=str(job.id),
        payload={
            "provider_event_id": receipt.provider_event_id,
            "previous_provider_event_id": job.provider_event_id,
            "operation": job.operation,
            "generation": job.generation,
        },
    )


def run_calendar_booking_batch(
    session: Session, *, provider: CalendarProvider, limit: int = 25
) -> int:
    processed = 0
    for _ in range(limit):
        job = _claim(session, now=datetime.now(timezone.utc))
        if job is None:
            break
        try:
            command = _prepare_command(
                session, job=job, provider=provider, now=datetime.now(timezone.utc)
            )
            reservation = None
            if job.operation == "BOOK":
                request_id = _request_id_for_confirmation(session, job.confirmation_id)
                reservation = reserve_capacity(
                    session,
                    tenant_id=job.tenant_id,
                    workspace_id=job.workspace_id,
                    deployment_id=job.deployment_id,
                    capacity_metric="confirmed_meeting",
                    idempotency_key=f"calendar-workflow:{request_id}",
                )
            elif job.usage_reservation_id is None:
                raise CalendarBookingError("lifecycle capacity reservation is required")
            envelope = command.model_dump(mode="json")
            job.command_envelope = {**envelope, "provider": "CALENDLY"}
            job.command_digest = command.command_digest
            if reservation is not None:
                job.usage_reservation_id = reservation.id
            session.add(job)
            session.commit()
        except CalendarSlotUnavailable as exc:
            session.rollback()
            current = session.get(CalendarBookingJob, job.id)
            if current is not None:
                current.status = "INPUT_REQUIRED"
                current.lease_token = None
                current.lease_expires_at = None
                current.last_error_code = type(exc).__name__
                session.add(current)
                session.commit()
            processed += 1
            continue
        except Exception as exc:
            session.rollback()
            current = session.get(CalendarBookingJob, job.id)
            if current is not None:
                current.status = (
                    "DEAD_LETTER"
                    if current.attempt_count >= current.max_attempts
                    else "RETRY_SCHEDULED"
                )
                current.available_at = datetime.now(timezone.utc) + timedelta(
                    minutes=min(60, 2 ** max(0, current.attempt_count - 1))
                )
                current.lease_token = None
                current.lease_expires_at = None
                current.last_error_code = type(exc).__name__[:64]
                session.add(current)
                session.commit()
            processed += 1
            continue
        if _tenant_is_paused(session, job.tenant_id):
            current = session.get(CalendarBookingJob, job.id)
            if current is not None:
                current.status = "RETRY_SCHEDULED"
                current.available_at = datetime.now(timezone.utc) + timedelta(minutes=1)
                current.lease_token = None
                current.lease_expires_at = None
                current.last_error_code = "TENANT_PAUSED_BEFORE_PROVIDER_CALL"
                session.add(current)
                session.commit()
            processed += 1
            continue
        try:
            job.provider_attempted_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
            dispatch = {
                "BOOK": provider.create_event,
                "RESCHEDULE": provider.reschedule_event,
                "CANCEL": provider.cancel_event,
            }
            receipt = dispatch[job.operation](command)
        except Exception as exc:
            session.rollback()
            current = session.get(CalendarBookingJob, job.id)
            if current is not None and current.usage_reservation_id is not None:
                mark_capacity_unknown(
                    session,
                    reservation_id=current.usage_reservation_id,
                    reason=f"AMBIGUOUS_CALENDAR_OUTCOME:{type(exc).__name__}",
                )
                current.status = "UNKNOWN_PROVIDER_OUTCOME"
                current.lease_token = None
                current.lease_expires_at = None
                current.last_error_code = type(exc).__name__[:64]
                session.add(current)
                session.commit()
            processed += 1
            continue
        try:
            _finalize(
                session,
                job=job,
                receipt=receipt,
                now=datetime.now(timezone.utc),
            )
        except CalendarBookingError:
            session.rollback()
            current = session.get(CalendarBookingJob, job.id)
            if current is not None and current.usage_reservation_id is not None:
                mark_capacity_unknown(
                    session,
                    reservation_id=current.usage_reservation_id,
                    reason="CALENDAR_COMPLETION_LEASE_OR_RECEIPT_MISMATCH",
                )
                current.status = "UNKNOWN_PROVIDER_OUTCOME"
                current.lease_token = None
                current.lease_expires_at = None
                session.add(current)
                session.commit()
        processed += 1
    return processed


def recover_expired_booking_leases(
    session: Session, *, now: datetime | None = None
) -> int:
    at = _utc(now or datetime.now(timezone.utc))
    jobs = session.exec(
        select(CalendarBookingJob).where(
            CalendarBookingJob.status == "IN_PROGRESS",
            CalendarBookingJob.lease_expires_at < at,
        )
    ).all()
    for job in jobs:
        if job.provider_attempted_at is None:
            job.status = "RETRY_SCHEDULED"
            job.available_at = at
        else:
            if job.usage_reservation_id is not None:
                mark_capacity_unknown(
                    session,
                    reservation_id=job.usage_reservation_id,
                    reason="CALENDAR_WORKER_LEASE_EXPIRED_AFTER_PROVIDER_CALL",
                    now=at,
                )
            job.status = "UNKNOWN_PROVIDER_OUTCOME"
        job.lease_token = None
        job.lease_expires_at = None
        job.updated_at = at
        session.add(job)
    session.flush()
    return len(jobs)


def reconcile_unknown_booking(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    job_id: uuid.UUID,
    provider: CalendarProvider,
    actor_id: uuid.UUID,
    actor_role: str,
    capabilities: set[str],
    provider_accepted: bool = True,
    provider_evidence_id: str | None = None,
    reason: str = "calendar provider outcome reconciled",
) -> CalendarBookingJob:
    """Finalize a receipt-backed ambiguous booking without invoking create again."""

    if "agents.admin.manage" not in capabilities:
        raise CalendarBookingError("agent administration capability is required")
    job = session.exec(
        select(CalendarBookingJob)
        .where(
            CalendarBookingJob.id == job_id,
            CalendarBookingJob.tenant_id == tenant_id,
            CalendarBookingJob.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if (
        job is None
        or job.status != "UNKNOWN_PROVIDER_OUTCOME"
        or job.usage_reservation_id is None
        or job.command_digest is None
    ):
        raise CalendarBookingError("unknown calendar booking was not found")
    receipt = provider.lookup_event(
        job.command_key,
        str((job.command_envelope or {}).get("credential_secret_ref", "")),
    )
    evidence_id = (provider_evidence_id or "").strip()
    if provider_accepted and receipt is None:
        raise CalendarBookingError("accepted outcome requires a provider receipt")
    if not provider_accepted and receipt is not None:
        raise CalendarBookingError("provider reports an accepted event; do not replay")
    if not provider_accepted and not evidence_id:
        raise CalendarBookingError("negative reconciliation requires provider evidence")
    command = job.command_envelope or {}
    if receipt is not None and (
        receipt.command_key != job.command_key
        or _utc(receipt.starts_at)
        != _utc(
            datetime.fromisoformat(str(command.get("starts_at")).replace("Z", "+00:00"))
        )
        or _utc(receipt.ends_at)
        != _utc(
            datetime.fromisoformat(str(command.get("ends_at")).replace("Z", "+00:00"))
        )
    ):
        raise CalendarBookingError("provider receipt does not match booking command")
    reconcile_unknown_capacity(
        session,
        reservation_id=job.usage_reservation_id,
        accepted=provider_accepted,
        provider_receipt_id=(receipt.provider_receipt_id if receipt else evidence_id),
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason,
    )
    if receipt is not None:
        session.add(
            CalendarBookingReceipt(
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                confirmation_id=job.confirmation_id,
                provider=command.get("provider", "CALENDLY"),
                provider_event_id=receipt.provider_event_id,
                provider_receipt_id=receipt.provider_receipt_id,
                command_digest=job.command_digest,
            )
        )
        _sync_scheduling_request(
            session, job=job, receipt=receipt, now=datetime.now(timezone.utc)
        )
        job.status = "COMPLETED"
    else:
        job.status = "PENDING"
        job.command_envelope = None
        job.command_digest = None
        job.provider_attempted_at = None
        job.usage_reservation_id = None
        job.available_at = datetime.now(timezone.utc)
    job.last_error_code = None
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    append_audit_event_to_session(
        session,
        event_name="calendar_scheduler.meeting.reconciled",
        workspace_id=job.workspace_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type="calendar_booking_job",
        resource_id=str(job.id),
        payload={
            "provider_accepted": provider_accepted,
            "provider_evidence_id": (
                receipt.provider_receipt_id if receipt else evidence_id
            ),
        },
    )
    session.flush()
    return job


def replay_dead_letter_booking(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
    capabilities: set[str],
    reason: str,
) -> CalendarBookingJob:
    if "agents.admin.manage" not in capabilities or not reason.strip():
        raise CalendarBookingError(
            "agent administration and replay reason are required"
        )
    job = session.exec(
        select(CalendarBookingJob)
        .where(
            CalendarBookingJob.id == job_id,
            CalendarBookingJob.tenant_id == tenant_id,
            CalendarBookingJob.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if job is None or job.status != "DEAD_LETTER":
        raise CalendarBookingError("dead-letter calendar booking was not found")
    if job.provider_attempted_at is not None:
        raise CalendarBookingError("attempted provider commands require reconciliation")
    job.status = "PENDING"
    job.attempt_count = 0
    job.available_at = datetime.now(timezone.utc)
    job.last_error_code = None
    session.add(job)
    append_audit_event_to_session(
        session,
        event_name="calendar_scheduler.dead_letter.replayed",
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type="calendar_booking_job",
        resource_id=str(job.id),
        payload={"reason": reason.strip(), "tenant_id": str(tenant_id)},
    )
    session.flush()
    return job
