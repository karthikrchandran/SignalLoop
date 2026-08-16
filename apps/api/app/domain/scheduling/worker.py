"""Durable, lease-safe Calendar Scheduler Agent booking worker."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, update
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
from app.domain.tenants.models import ProductCode, TenantOperationalControl


class CalendarBookingError(ValueError):
    """A deterministic calendar booking state or ownership error."""


class CalendarSlotUnavailable(CalendarBookingError):
    """The selected slot became busy before provider invocation."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _claim(
    session: Session, *, now: datetime, lease_seconds: int = 300
) -> CalendarBookingJob | None:
    paused = exists(
        select(TenantOperationalControl.id).where(
            TenantOperationalControl.tenant_id == CalendarBookingJob.tenant_id,
            TenantOperationalControl.product_code == ProductCode.SIGNAL_LOOP.value,
            TenantOperationalControl.paused == True,  # noqa: E712
        )
    )
    candidate = session.exec(
        select(CalendarBookingJob.id)
        .where(
            CalendarBookingJob.status.in_(["PENDING", "RETRY_SCHEDULED"]),
            CalendarBookingJob.available_at <= now,
            ~paused,
        )
        .order_by(CalendarBookingJob.created_at, CalendarBookingJob.id)
        .limit(1)
    ).first()
    if candidate is None:
        return None
    token = uuid.uuid4()
    result = session.exec(
        update(CalendarBookingJob)
        .where(
            CalendarBookingJob.id == candidate,
            CalendarBookingJob.status.in_(["PENDING", "RETRY_SCHEDULED"]),
            CalendarBookingJob.available_at <= now,
            ~paused,
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
            CalendarBookingJob.id == candidate,
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
    slot = _selected_slot(offer, confirmation)
    starts_at = _utc(datetime.fromisoformat(slot["starts_at"]))
    ends_at = _utc(datetime.fromisoformat(slot["ends_at"]))
    if starts_at <= now:
        raise CalendarSlotUnavailable("selected slot is no longer in the future")
    busy = provider.free_busy(
        provider_account_ref=binding.provider_account_ref,
        start_date=starts_at.date(),
        end_date=ends_at.date(),
    )
    if any(_overlaps(starts_at, ends_at, interval) for interval in busy):
        raise CalendarSlotUnavailable("selected slot is no longer available")
    base = {
        "schema_version": "calendar-booking-command.v1",
        "command_key": job.command_key,
        "provider_account_ref": binding.provider_account_ref,
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
            provider=command.get("provider", "CALENDLY"),
            provider_event_id=receipt.provider_event_id,
            provider_receipt_id=receipt.provider_receipt_id,
            command_digest=job.command_digest,
            created_at=now,
        )
    )
    confirmation = session.get(SchedulingConfirmation, job.confirmation_id)
    if confirmation is not None:
        offer = session.get(SchedulingOffer, confirmation.offer_id)
        if offer is not None:
            request = session.get(SchedulingRequest, offer.scheduling_request_id)
            if request is not None and request.workspace_id == job.workspace_id:
                request.status = SchedulingRequestStatus.booked
                request.calendly_event_id = receipt.provider_event_id
                request.meeting_datetime = receipt.starts_at
                request.updated_at = now
                session.add(request)
    append_audit_event_to_session(
        session,
        event_name="calendar_scheduler.meeting.confirmed",
        workspace_id=job.workspace_id,
        resource_type="calendar_booking_job",
        resource_id=str(job.id),
        payload={"provider_event_id": receipt.provider_event_id},
    )
    session.commit()


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
            reservation = reserve_capacity(
                session,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                deployment_id=job.deployment_id,
                capacity_metric="confirmed_meeting",
                idempotency_key=f"calendar-booking:{job.id}",
            )
            envelope = command.model_dump(mode="json")
            job.command_envelope = {**envelope, "provider": "CALENDLY"}
            job.command_digest = command.command_digest
            job.usage_reservation_id = reservation.id
            job.provider_attempted_at = datetime.now(timezone.utc)
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
        try:
            receipt = provider.create_event(command)
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
    receipt = provider.lookup_event(job.command_key)
    if receipt is None:
        raise CalendarBookingError("provider receipt is unavailable; do not replay")
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
    reconcile_unknown_capacity(
        session,
        reservation_id=job.usage_reservation_id,
        accepted=True,
        provider_receipt_id=receipt.provider_receipt_id,
        actor_id=actor_id,
        actor_role=actor_role,
        reason="calendar provider receipt reconciled",
    )
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
    job.status = "COMPLETED"
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
        payload={"provider_event_id": receipt.provider_event_id},
    )
    session.commit()
    return job
