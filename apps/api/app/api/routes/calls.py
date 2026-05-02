"""Call review screen — list, detail, and manual action endpoints."""
from __future__ import annotations

import html
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import SQLModel, func, select

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.core.config import settings
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
)
from app.domain.voice.models import (
    CallRequest,
    CallSession,
)
from app.domain_models import Campaign, Contact
from app.infrastructure.providers.sendgrid import SendGridAdapter

router = APIRouter(prefix="/calls", tags=["calls"], dependencies=[Depends(require_admin)])


class CallListItem(SQLModel):
    call_request_id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    status: str
    outcome: str | None
    duration_seconds: int | None
    scheduled_at: datetime | None
    created_at: datetime


class CallListPublic(SQLModel):
    data: list[CallListItem]
    count: int


class CallDetailPublic(SQLModel):
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


@router.get("/", response_model=CallListPublic)
def list_calls(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID | None = None,
    outcome: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> CallListPublic:
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
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    req = _get_call_request_or_404(session, call_request_id, workspace_id)

    contact = session.get(Contact, req.contact_id)
    if not contact or contact.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    adapter = SendGridAdapter()
    name = contact.first_name or "there"
    await adapter.send_email(
        to=contact.email,
        subject="Thanks for your time — here's your demo access",
        body_html=f"<p>Hi {html.escape(name)},</p><p>Following up on our call — here's your demo access.</p>",
        body_text=f"Hi {name}, following up on our call — here's your demo access.",
    )
    return {"message": "Demo email sent"}


@router.post("/{call_request_id}/flag-for-sales")
async def flag_for_sales(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    call_request_id: uuid.UUID,
) -> dict[str, str]:
    req = _get_call_request_or_404(session, call_request_id, workspace_id)

    contact = session.get(Contact, req.contact_id)
    if not contact or contact.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Contact not found")

    adapter = SendGridAdapter()
    team_email = settings.TEAM_NOTIFICATION_EMAIL
    if not team_email:
        raise HTTPException(status_code=500, detail="Team notification email not configured")

    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "Unknown"
    await adapter.send_email(
        to=team_email,
        subject=f"[SALES FLAG] {name} flagged for follow-up",
        body_html=f"<p><strong>{html.escape(name)}</strong> ({html.escape(contact.email)}) has been flagged for sales follow-up.</p>",
        body_text=f"{name} ({contact.email}) flagged for sales follow-up.",
    )
    return {"message": "Contact flagged for sales team"}


@router.post("/{call_request_id}/pause-sequence")
def pause_contact_sequence(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
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

    session.commit()
    return {"message": f"Paused {paused} active sequence(s)"}
