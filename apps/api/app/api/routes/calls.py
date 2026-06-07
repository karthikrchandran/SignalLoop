"""Call review screen — list, detail, and manual action endpoints."""
from __future__ import annotations

import html
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import SQLModel, func, select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.outreach.outbox_service import (
    enqueue_outbox_event,
    mark_outbox_published,
)
from app.domain.runtime_settings import resolve_team_notification_email
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
)
from app.domain.voice.models import (
    CallRequest,
    CallSession,
)
from app.domain_models import Campaign, Contact, OutboxEvent
from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.registry import resolve_email_adapter
from app.infrastructure.providers.sendgrid import SendGridAdapter

router = APIRouter(prefix="/calls", tags=["calls"], dependencies=[Depends(require_admin)])


class CallListItem(SQLModel):
    """List item: call list."""
    call_request_id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    status: str
    outcome: str | None
    duration_seconds: int | None
    scheduled_at: datetime | None
    created_at: datetime


class CallListPublic(SQLModel):
    """API response model: call list."""
    data: list[CallListItem]
    count: int


class CallDetailPublic(SQLModel):
    """API response model: call detail."""
    call_request_id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    status: str
    trigger_reason: str | None
    outcome: str | None
    duration_seconds: int | None
    recording_url: str | None
    transcript: str | None
    unanswered_questions: list[str] | None
    scheduling_interest: bool | None
    scheduled_at: datetime | None


def _get_call_request_or_404(
    session: SessionDep,
    call_request_id: uuid.UUID,
    workspace_id: str,
) -> CallRequest:
    req = session.exec(
        select(CallRequest)
        .join(Campaign, CallRequest.campaign_id == Campaign.id)
        .where(
            CallRequest.id == call_request_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Call not found")
    return req


def _call_action_intent_key(call_request_id: uuid.UUID, action: str) -> str:
    return f"call_request:{call_request_id}:{action}"


def _provider_send_accepted(result: dict) -> bool:
    status_code = int(result.get("status_code") or 0)
    return 200 <= status_code < 300


def _raise_call_action_in_progress(action: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": {
                "code": "CALL_ACTION_IN_PROGRESS",
                "message": f"Call action '{action}' is already in progress",
                "semantic": "POLICY_VIOLATION",
                "details": {"action": action},
            }
        },
    )


def _prepare_call_action_intent(
    session: SessionDep,
    *,
    call_request_id: uuid.UUID,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    action: str,
    event_type: str,
    event_data: dict,
) -> OutboxEvent | None:
    intent_key = _call_action_intent_key(call_request_id, action)
    existing = session.exec(
        select(OutboxEvent).where(OutboxEvent.idempotency_key == intent_key)
    ).first()
    if existing:
        if existing.published_at is not None:
            return None
        _raise_call_action_in_progress(action)

    return enqueue_outbox_event(
        session,
        aggregate_id=call_request_id,
        aggregate_type="call_request",
        event_type=event_type,
        event_data={
            "call_request_id": str(call_request_id),
            "contact_id": str(contact_id),
            "campaign_id": str(campaign_id),
            **event_data,
        },
        idempotency_key=intent_key,
    )


def _email_adapter(session: SessionDep, workspace_id: str) -> EmailAdapter:
    return resolve_email_adapter(
        session,
        workspace_id,
        default_factory=SendGridAdapter,
    )


@router.get("/", response_model=CallListPublic)
def list_calls(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID | None = None,
    outcome: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> CallListPublic:
    """Return a list of calls."""
    query = (
        select(CallRequest, CallSession)
        .join(Campaign, CallRequest.campaign_id == Campaign.id)
        .outerjoin(CallSession, CallRequest.id == CallSession.call_request_id)
        .where(Campaign.workspace_id == workspace_id)
    )
    count_query = (
        select(func.count(CallRequest.id))
        .join(Campaign, CallRequest.campaign_id == Campaign.id)
        .where(Campaign.workspace_id == workspace_id)
    )

    if campaign_id:
        query = query.where(CallRequest.campaign_id == campaign_id)
        count_query = count_query.where(CallRequest.campaign_id == campaign_id)
    if outcome:
        # Use inner join instead of the base outerjoin when filtering by outcome
        query = (
            select(CallRequest, CallSession)
            .join(Campaign, CallRequest.campaign_id == Campaign.id)
            .join(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(Campaign.workspace_id == workspace_id, CallSession.outcome == outcome)
        )
        count_query = (
            select(func.count(CallRequest.id))
            .join(Campaign, CallRequest.campaign_id == Campaign.id)
            .join(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(Campaign.workspace_id == workspace_id, CallSession.outcome == outcome)
        )
        if campaign_id:
            query = query.where(CallRequest.campaign_id == campaign_id)
            count_query = count_query.where(CallRequest.campaign_id == campaign_id)

    total = session.exec(count_query).one()
    results = session.exec(
        query.order_by(CallRequest.created_at.desc()).offset(skip).limit(limit)
    ).all()

    data = []
    for req, sess in results:
        data.append(
            CallListItem(
                call_request_id=req.id,
                contact_id=req.contact_id,
                campaign_id=req.campaign_id,
                status=req.status.value if req.status else "unknown",
                outcome=sess.outcome.value if sess and sess.outcome else None,
                duration_seconds=sess.duration_seconds if sess else None,
                scheduled_at=req.scheduled_at,
                created_at=req.created_at,
            )
        )

    return CallListPublic(data=data, count=total)


@router.get("/{call_request_id}", response_model=CallDetailPublic)
def get_call_detail(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    call_request_id: uuid.UUID,
) -> CallDetailPublic:
    """Return call detail."""
    req = _get_call_request_or_404(session, call_request_id, workspace_id)

    sess = session.exec(
        select(CallSession).where(CallSession.call_request_id == req.id)
    ).first()

    return CallDetailPublic(
        call_request_id=req.id,
        contact_id=req.contact_id,
        campaign_id=req.campaign_id,
        status=req.status.value if req.status else "unknown",
        trigger_reason=req.trigger_reason,
        outcome=sess.outcome.value if sess and sess.outcome else None,
        duration_seconds=sess.duration_seconds if sess else None,
        recording_url=sess.recording_url if sess else None,
        transcript=sess.transcript if sess else None,
        unanswered_questions=sess.unanswered_questions if sess else None,
        scheduling_interest=sess.scheduling_interest if sess else None,
        scheduled_at=req.scheduled_at,
    )


@router.post("/{call_request_id}/send-demo-email")
async def send_demo_email(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    """Send demo email."""
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation=f"calls:{call_request_id}:send-demo-email",
        request_payload={"call_request_id": str(call_request_id)},
        mutation=lambda: _send_demo_email_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            call_request_id=call_request_id,
        ),
    )


async def _send_demo_email_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    req = _get_call_request_or_404(session, call_request_id, workspace_id)

    contact = session.get(Contact, req.contact_id)
    if not contact or contact.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    name = contact.first_name or "there"
    intent = _prepare_call_action_intent(
        session,
        call_request_id=call_request_id,
        contact_id=contact.id,
        campaign_id=req.campaign_id,
        action="send_demo_email",
        event_type="call.demo_email_send_requested",
        event_data={"to": contact.email},
    )
    if intent is None:
        return {"message": "Demo email already sent"}

    adapter = _email_adapter(session, workspace_id)
    result = await adapter.send_email(
        to=contact.email,
        subject="Thanks for your time — here's your demo access",
        body_html=f"<p>Hi {html.escape(name)},</p><p>Following up on our call — here's your demo access.</p>",
        body_text=f"Hi {name}, following up on our call — here's your demo access.",
        idempotency_key=intent.idempotency_key,
    )
    if not _provider_send_accepted(result):
        raise HTTPException(status_code=502, detail="Email provider rejected demo email")

    append_audit_event_to_session(
        session,
        event_name="call.demo_email_sent",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="call_request",
        resource_id=str(call_request_id),
        payload={
            "call_request_id": str(call_request_id),
            "contact_id": str(contact.id),
            "campaign_id": str(req.campaign_id),
        },
    )
    mark_outbox_published(session, event_id=intent.id)
    return {"message": "Demo email sent"}


@router.post("/{call_request_id}/flag-for-sales")
async def flag_for_sales(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    """Flag for sales."""
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation=f"calls:{call_request_id}:flag-for-sales",
        request_payload={"call_request_id": str(call_request_id)},
        mutation=lambda: _flag_for_sales_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            call_request_id=call_request_id,
        ),
    )


async def _flag_for_sales_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    req = _get_call_request_or_404(session, call_request_id, workspace_id)

    contact = session.get(Contact, req.contact_id)
    if not contact or contact.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    team_email = resolve_team_notification_email(session, workspace_id)
    if not team_email:
        raise HTTPException(status_code=500, detail="Team notification email not configured")

    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "Unknown"
    intent = _prepare_call_action_intent(
        session,
        call_request_id=call_request_id,
        contact_id=contact.id,
        campaign_id=req.campaign_id,
        action="flag_for_sales",
        event_type="call.sales_flag_email_requested",
        event_data={"to": team_email},
    )
    if intent is None:
        return {"message": "Contact already flagged for sales team"}

    adapter = _email_adapter(session, workspace_id)
    result = await adapter.send_email(
        to=team_email,
        subject=f"[SALES FLAG] {name} flagged for follow-up",
        body_html=f"<p><strong>{html.escape(name)}</strong> ({html.escape(contact.email)}) has been flagged for sales follow-up.</p>",
        body_text=f"{name} ({contact.email}) flagged for sales follow-up.",
        idempotency_key=intent.idempotency_key,
    )
    if not _provider_send_accepted(result):
        raise HTTPException(status_code=502, detail="Email provider rejected sales flag")

    append_audit_event_to_session(
        session,
        event_name="call.flagged_for_sales",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="call_request",
        resource_id=str(call_request_id),
        payload={
            "call_request_id": str(call_request_id),
            "contact_id": str(contact.id),
            "campaign_id": str(req.campaign_id),
        },
    )
    mark_outbox_published(session, event_id=intent.id)
    return {"message": "Contact flagged for sales team"}


@router.post("/{call_request_id}/pause-sequence")
async def pause_contact_sequence(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    """Pause contact sequence."""
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation=f"calls:{call_request_id}:pause-sequence",
        request_payload={"call_request_id": str(call_request_id)},
        mutation=lambda: _pause_contact_sequence_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            call_request_id=call_request_id,
        ),
    )


def _pause_contact_sequence_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    req = _get_call_request_or_404(session, call_request_id, workspace_id)

    # Pause any active sequences for this contact
    states = session.exec(
        select(ContactSequenceState)
        .join(EmailSequence, ContactSequenceState.sequence_id == EmailSequence.id)
        .join(Campaign, EmailSequence.campaign_id == Campaign.id)
        .where(
            ContactSequenceState.contact_id == req.contact_id,
            ContactSequenceState.status == SequenceStatus.active,
            Campaign.workspace_id == workspace_id,
        )
    ).all()

    paused = 0
    for state in states:
        state.status = SequenceStatus.paused
        session.add(state)
        paused += 1

    append_audit_event_to_session(
        session,
        event_name="call.sequence_paused",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="call_request",
        resource_id=str(call_request_id),
        payload={
            "call_request_id": str(call_request_id),
            "contact_id": str(req.contact_id),
            "campaign_id": str(req.campaign_id),
            "paused_sequence_count": paused,
        },
    )
    session.commit()
    return {"message": f"Paused {paused} active sequence(s)"}
