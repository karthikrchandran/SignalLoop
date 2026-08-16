"""FastAPI router: ``scheduling`` endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.api.routes.commercial_agents import _authorize_agent_admin
from app.core.config import settings
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.commercial_agents.models import (
    AgentDeployment,
    AgentDeploymentStatus,
    AgentType,
)
from app.domain.scheduling import service as scheduling_service
from app.domain.scheduling.availability import (
    AvailabilityPolicy,
    calculate_available_slots,
)
from app.domain.scheduling.models import (
    CalendarBookingJob,
    CalendarMeetingType,
    CalendarProviderBinding,
    SchedulingRequest,
)
from app.domain.scheduling.providers import (
    CalendarProvider,
    CalendarProviderConfigurationError,
    load_calendar_provider,
)
from app.domain.scheduling.schemas import (
    CalendarCancellationCreate,
    CalendarConfirmationCreate,
    CalendarMeetingTypeCreate,
    CalendarOfferCreate,
    CalendarProviderBindingCreate,
    CalendarReconciliationCreate,
    CalendarReplayCreate,
    SchedulingRequestCreate,
    SchedulingRequestPublic,
    SchedulingRequestsPublic,
    SchedulingRequestUpdate,
)
from app.domain.scheduling.worker import (
    CalendarBookingError,
    enqueue_calendar_lifecycle_job,
    reconcile_unknown_booking,
    replay_dead_letter_booking,
)
from app.domain.tenants.models import TenantWorkspaceBinding
from app.domain_models import Campaign

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduling", tags=["scheduling"])


def _calendar_provider() -> CalendarProvider:
    try:
        return load_calendar_provider()
    except CalendarProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _require_tenant_workspace(session, tenant_id: uuid.UUID, workspace_id: str) -> None:
    binding = session.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.tenant_id == tenant_id,
            TenantWorkspaceBinding.workspace_id == workspace_id,
            TenantWorkspaceBinding.status == "ACTIVE",
        )
    ).one_or_none()
    if binding is None:
        raise HTTPException(status_code=404, detail="Tenant workspace not found")


def _public_request(req: object) -> SchedulingRequestPublic:
    public = SchedulingRequestPublic.model_validate(req)
    public.calendly_state = scheduling_service.mint_calendly_state(
        public.id,
        public.workspace_id,
        settings.SECRET_KEY,
        ttl_seconds=settings.CALENDLY_STATE_TTL_SECONDS,
    )
    return public


# ---------------------------------------------------------------------------
# List / detail / update
# ---------------------------------------------------------------------------


@router.get("/requests", response_model=SchedulingRequestsPublic)
def list_requests(
    session: SessionDep,
    _current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    status_filter: str | None = Query(default=None, alias="status"),
    campaign_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
) -> SchedulingRequestsPublic:
    """List scheduling requests for the workspace."""
    rows, total = scheduling_service.list_scheduling_requests(
        session,
        workspace_id=workspace_id,
        status=status_filter,
        campaign_id=campaign_id,
        skip=skip,
        limit=limit,
    )
    return SchedulingRequestsPublic(
        data=[_public_request(r) for r in rows],
        count=total,
    )


@router.get("/requests/{request_id}", response_model=SchedulingRequestPublic)
def get_request(
    request_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
) -> SchedulingRequestPublic:
    """Get a single scheduling request."""
    req = scheduling_service.get_scheduling_request_or_404(session, request_id)
    # Verify workspace ownership
    campaign = session.get(Campaign, req.campaign_id)
    if not campaign or campaign.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Scheduling request not found")
    return _public_request(req)


@router.post(
    "/requests",
    response_model=SchedulingRequestPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_request(
    data: SchedulingRequestCreate,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
) -> SchedulingRequestPublic:
    """Manually create a scheduling request."""
    campaign = session.exec(
        select(Campaign).where(
            Campaign.id == data.campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    req = scheduling_service.create_scheduling_request(session, data=data)
    append_audit_event_to_session(
        session,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        event_type="scheduling_request.created",
        aggregate_id=req.id,
        aggregate_type="SchedulingRequest",
        workspace_id=workspace_id,
        details={"source": data.source},
    )
    session.commit()
    session.refresh(req)
    return _public_request(req)


@router.patch("/requests/{request_id}", response_model=SchedulingRequestPublic)
def update_request(
    request_id: uuid.UUID,
    data: SchedulingRequestUpdate,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
) -> SchedulingRequestPublic:
    """Update status, meeting link, assignee, or notes on a scheduling request."""
    req = scheduling_service.get_scheduling_request_or_404(session, request_id)
    campaign = session.get(Campaign, req.campaign_id)
    if not campaign or campaign.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Scheduling request not found")

    updated = scheduling_service.update_scheduling_request(
        session, request_id=request_id, data=data
    )
    append_audit_event_to_session(
        session,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        event_type="scheduling_request.updated",
        aggregate_id=updated.id,
        aggregate_type="SchedulingRequest",
        workspace_id=workspace_id,
        details=data.model_dump(exclude_none=True),
    )
    session.commit()
    session.refresh(updated)
    return _public_request(updated)


# ---------------------------------------------------------------------------
# Autonomous Calendar Scheduler Agent
# ---------------------------------------------------------------------------


@router.post("/agent/tenants/{tenant_id}/meeting-types", status_code=201)
async def create_meeting_type(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarMeetingTypeCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)
    AvailabilityPolicy(
        timezone=data.timezone,
        duration_minutes=data.duration_minutes,
        working_hours=data.working_hours,
        holiday_dates=set(data.holiday_dates),
        buffer_before_minutes=data.buffer_before_minutes,
        buffer_after_minutes=data.buffer_after_minutes,
        minimum_notice_minutes=data.minimum_notice_minutes,
    )

    def create_once() -> dict[str, Any]:
        if session.exec(
            select(CalendarMeetingType.id).where(
                CalendarMeetingType.tenant_id == tenant_id,
                CalendarMeetingType.workspace_id == data.workspace_id,
                CalendarMeetingType.name == data.name,
            )
        ).first():
            raise HTTPException(status_code=409, detail="Meeting type already exists")
        row = CalendarMeetingType(
            tenant_id=tenant_id,
            workspace_id=data.workspace_id,
            **data.model_dump(exclude={"workspace_id", "holiday_dates"}),
            holiday_dates=[value.isoformat() for value in data.holiday_dates],
        )
        session.add(row)
        session.flush()
        append_audit_event_to_session(
            session,
            event_name="calendar_scheduler.meeting_type.created",
            workspace_id=data.workspace_id,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
            resource_type="calendar_meeting_type",
            resource_id=str(row.id),
            payload={"tenant_id": str(tenant_id), "name": row.name},
        )
        return {"id": str(row.id), "status": row.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation="calendar-scheduler:meeting-type:create",
        request_payload=data.model_dump(mode="json"),
        mutation=create_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/agent/tenants/{tenant_id}/provider-bindings", status_code=201)
async def create_provider_binding(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarProviderBindingCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)
    required = {"free_busy.read", "event.create", "event.lookup"}
    if not required.issubset(data.capabilities):
        raise HTTPException(
            status_code=409, detail="Calendar capabilities are incomplete"
        )

    def create_once() -> dict[str, Any]:
        row = CalendarProviderBinding(
            tenant_id=tenant_id,
            workspace_id=data.workspace_id,
            provider=data.provider,
            provider_account_ref=data.provider_account_ref,
            credential_secret_ref=data.credential_secret_ref,
            capabilities=sorted(data.capabilities),
        )
        session.add(row)
        session.flush()
        append_audit_event_to_session(
            session,
            event_name="calendar_scheduler.provider_binding.created",
            workspace_id=data.workspace_id,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
            resource_type="calendar_provider_binding",
            resource_id=str(row.id),
            payload={"tenant_id": str(tenant_id), "provider": row.provider},
        )
        return {"id": str(row.id), "status": row.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation="calendar-scheduler:provider-binding:create",
        request_payload=data.model_dump(mode="json"),
        mutation=create_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/agent/tenants/{tenant_id}/requests/{request_id}/offers", status_code=201)
async def create_calendar_offer(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    request_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarOfferCreate,
    idempotency_key: IdempotencyKeyDep,
    provider: CalendarProvider = Depends(_calendar_provider),
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)
    meeting_type = session.exec(
        select(CalendarMeetingType).where(
            CalendarMeetingType.id == data.meeting_type_id,
            CalendarMeetingType.tenant_id == tenant_id,
            CalendarMeetingType.workspace_id == data.workspace_id,
            CalendarMeetingType.status == "ACTIVE",
        )
    ).one_or_none()
    binding = session.exec(
        select(CalendarProviderBinding).where(
            CalendarProviderBinding.tenant_id == tenant_id,
            CalendarProviderBinding.workspace_id == data.workspace_id,
            CalendarProviderBinding.status == "ACTIVE",
        )
    ).one_or_none()
    owned_request = session.exec(
        select(SchedulingRequest.id).where(
            SchedulingRequest.id == request_id,
            SchedulingRequest.workspace_id == data.workspace_id,
        )
    ).one_or_none()
    if meeting_type is None or binding is None or owned_request is None:
        raise HTTPException(status_code=404, detail="Calendar configuration not found")
    start_date = data.start_date
    end_date = data.end_date
    policy = AvailabilityPolicy(
        timezone=meeting_type.timezone,
        duration_minutes=meeting_type.duration_minutes,
        working_hours=meeting_type.working_hours,
        holiday_dates={
            date.fromisoformat(value) for value in meeting_type.holiday_dates
        },
        buffer_before_minutes=meeting_type.buffer_before_minutes,
        buffer_after_minutes=meeting_type.buffer_after_minutes,
        minimum_notice_minutes=meeting_type.minimum_notice_minutes,
    )

    def create_once() -> dict[str, Any]:
        busy = provider.free_busy(
            provider_account_ref=binding.provider_account_ref,
            credential_secret_ref=binding.credential_secret_ref,
            start_date=start_date,
            end_date=end_date,
        )
        slots = calculate_available_slots(
            policy=policy,
            start_date=start_date,
            end_date=end_date,
            busy=busy,
            limit=data.limit,
        )
        if not slots:
            raise HTTPException(status_code=409, detail="No available slots")
        offer = scheduling_service.create_scheduling_offer(
            session,
            tenant_id=tenant_id,
            workspace_id=data.workspace_id,
            request_id=request_id,
            meeting_type_id=data.meeting_type_id,
            slots=slots,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=data.expires_in_minutes),
        )
        return {
            "id": str(offer.id),
            "version": offer.version,
            "offer_digest": offer.offer_digest,
            "slots": offer.slots,
            "expires_at": offer.expires_at.isoformat(),
        }

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation=f"calendar-scheduler:request:{request_id}:offer:create",
        request_payload=data.model_dump(mode="json"),
        mutation=create_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/agent/tenants/{tenant_id}/offers/{offer_id}/confirm", status_code=201)
async def confirm_calendar_offer(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    offer_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarConfirmationCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)

    def confirm_once() -> dict[str, Any]:
        deployment = session.exec(
            select(AgentDeployment).where(
                AgentDeployment.id == data.deployment_id,
                AgentDeployment.tenant_id == tenant_id,
                AgentDeployment.workspace_id == data.workspace_id,
                AgentDeployment.agent_type == AgentType.CALENDAR_SCHEDULER,
                AgentDeployment.status == AgentDeploymentStatus.ACTIVE,
            )
        ).one_or_none()
        binding = session.exec(
            select(CalendarProviderBinding).where(
                CalendarProviderBinding.id == data.binding_id,
                CalendarProviderBinding.tenant_id == tenant_id,
                CalendarProviderBinding.workspace_id == data.workspace_id,
                CalendarProviderBinding.status == "ACTIVE",
            )
        ).one_or_none()
        if deployment is None or binding is None:
            raise HTTPException(status_code=404, detail="Calendar agent not found")
        confirmation = scheduling_service.confirm_scheduling_offer(
            session,
            tenant_id=tenant_id,
            workspace_id=data.workspace_id,
            offer_id=offer_id,
            selected_slot_digest=data.selected_slot_digest,
            confirmed_by=data.confirmed_by,
            confirmation_key=idempotency_key,
        )
        try:
            job = enqueue_calendar_lifecycle_job(
                session,
                tenant_id=tenant_id,
                workspace_id=data.workspace_id,
                deployment_id=deployment.id,
                binding_id=binding.id,
                confirmation_id=confirmation.id,
                operation=data.operation,
                predecessor_job_id=data.predecessor_job_id,
            )
        except CalendarBookingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        append_audit_event_to_session(
            session,
            event_name="calendar_scheduler.offer.confirmed",
            workspace_id=data.workspace_id,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
            resource_type="calendar_booking_job",
            resource_id=str(job.id),
            payload={
                "offer_id": str(offer_id),
                "tenant_id": str(tenant_id),
                "operation": job.operation,
                "generation": job.generation,
            },
        )
        return {
            "confirmation_id": str(confirmation.id),
            "job_id": str(job.id),
            "status": job.status,
        }

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation=f"calendar-scheduler:offer:{offer_id}:confirm",
        request_payload=data.model_dump(mode="json"),
        mutation=confirm_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/agent/tenants/{tenant_id}/jobs/{job_id}/cancel", status_code=201)
async def cancel_calendar_job(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarCancellationCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)

    def cancel_once() -> dict[str, Any]:
        predecessor = session.exec(
            select(CalendarBookingJob).where(
                CalendarBookingJob.id == job_id,
                CalendarBookingJob.tenant_id == tenant_id,
                CalendarBookingJob.workspace_id == data.workspace_id,
            )
        ).one_or_none()
        if predecessor is None:
            raise HTTPException(status_code=404, detail="Calendar job not found")
        try:
            job = enqueue_calendar_lifecycle_job(
                session,
                tenant_id=tenant_id,
                workspace_id=data.workspace_id,
                deployment_id=predecessor.deployment_id,
                binding_id=predecessor.binding_id,
                confirmation_id=predecessor.confirmation_id,
                operation="CANCEL",
                predecessor_job_id=predecessor.id,
            )
        except CalendarBookingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        append_audit_event_to_session(
            session,
            event_name="calendar_scheduler.cancellation.requested",
            workspace_id=data.workspace_id,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
            resource_type="calendar_booking_job",
            resource_id=str(job.id),
            payload={"reason": data.reason, "generation": job.generation},
        )
        return {"job_id": str(job.id), "status": job.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation=f"calendar-scheduler:job:{job_id}:cancel",
        request_payload=data.model_dump(mode="json"),
        mutation=cancel_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/agent/tenants/{tenant_id}/jobs/{job_id}/reconcile")
async def reconcile_calendar_job(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarReconciliationCreate,
    idempotency_key: IdempotencyKeyDep,
    provider: CalendarProvider = Depends(_calendar_provider),
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)

    def reconcile_once() -> dict[str, Any]:
        try:
            job = reconcile_unknown_booking(
                session,
                tenant_id=tenant_id,
                workspace_id=data.workspace_id,
                job_id=job_id,
                provider=provider,
                actor_id=current_user.id,
                actor_role=audit_actor_role(current_user),
                capabilities={"agents.admin.manage"},
                provider_accepted=data.provider_accepted,
                provider_evidence_id=data.provider_evidence_id,
                reason=data.reason,
            )
        except CalendarBookingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"job_id": str(job.id), "status": job.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation=f"calendar-scheduler:job:{job_id}:reconcile",
        request_payload=data.model_dump(mode="json"),
        mutation=reconcile_once,
        safe_to_retry_on_failure=False,
    )


@router.post("/agent/tenants/{tenant_id}/jobs/{job_id}/replay")
async def replay_calendar_job(
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    header_workspace_id: WorkspaceIdDep,
    data: CalendarReplayCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, current_user, tenant_id)
    if data.workspace_id != header_workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace header and payload differ"
        )
    _require_tenant_workspace(session, tenant_id, data.workspace_id)

    def replay_once() -> dict[str, Any]:
        try:
            job = replay_dead_letter_booking(
                session,
                tenant_id=tenant_id,
                workspace_id=data.workspace_id,
                job_id=job_id,
                actor_id=current_user.id,
                actor_role=audit_actor_role(current_user),
                capabilities={"agents.admin.manage"},
                reason=data.reason,
            )
        except CalendarBookingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"job_id": str(job.id), "status": job.status}

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=header_workspace_id,
        operation=f"calendar-scheduler:job:{job_id}:replay",
        request_payload=data.model_dump(mode="json"),
        mutation=replay_once,
        safe_to_retry_on_failure=True,
    )


# ---------------------------------------------------------------------------
# Calendly webhook
# ---------------------------------------------------------------------------


@router.post("/webhooks/calendly", status_code=status.HTTP_200_OK)
async def calendly_webhook(
    request: Request,
    session: SessionDep,
) -> dict[str, str]:
    """Receive Calendly invitee.created events and mark the linked request as booked."""
    body = await request.body()
    signature = request.headers.get("Calendly-Webhook-Signature", "")

    signing_key = settings.CALENDLY_WEBHOOK_SIGNING_KEY
    if not signing_key:
        raise HTTPException(
            status_code=503, detail="Calendly webhook signing key is not configured"
        )
    if not scheduling_service.verify_calendly_signature(
        body,
        signature,
        signing_key,
        max_age_seconds=settings.CALENDLY_WEBHOOK_MAX_AGE_SECONDS,
    ):
        raise HTTPException(
            status_code=403, detail="Invalid Calendly webhook signature"
        )

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event", "")
    if event_type not in {"invitee.created", "invitee.canceled"}:
        # Acknowledge non-booking events without action
        return {"status": "ignored", "event": event_type}

    event_payload = payload.get("payload", {})
    tracking = event_payload.get("tracking", {})

    state_token = str(tracking.get("utm_content") or "").strip()
    if not state_token:
        logger.warning(
            "Calendly webhook: no utm_content in tracking, cannot link request"
        )
        return {"status": "unlinked"}
    state = scheduling_service.verify_calendly_state(state_token, settings.SECRET_KEY)
    if state is None:
        raise HTTPException(
            status_code=403, detail="Invalid or expired scheduling state"
        )
    request_id, workspace_id = state

    calendly_event = event_payload.get("event", {})
    event_uri = calendly_event.get("uri", "")
    start_time_str = calendly_event.get("start_time")
    try:
        meeting_dt = (
            datetime.fromisoformat(start_time_str)
            if start_time_str
            else datetime.now(timezone.utc)
        )
    except (ValueError, TypeError):
        meeting_dt = datetime.now(timezone.utc)

    if event_type == "invitee.canceled":
        scheduling_service.handle_calendly_cancellation(
            session,
            workspace_id=workspace_id,
            request_id=request_id,
            calendly_event_id=event_uri,
        )
        return {"status": "cancelled"}
    scheduling_service.handle_calendly_booking(
        session,
        workspace_id=workspace_id,
        request_id=request_id,
        calendly_event_id=event_uri,
        meeting_datetime=meeting_dt,
    )

    logger.info("Calendly booking confirmed for scheduling_request=%s", request_id)
    return {"status": "booked"}
