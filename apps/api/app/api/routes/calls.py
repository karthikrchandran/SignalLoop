"""Call review screen — list, detail, and manual action endpoints."""

from __future__ import annotations

import html
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import SQLModel, func, select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.config import settings  # noqa: F401  (test-time shared-record toggle)
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.outreach.outbox_service import (
    enqueue_outbox_event,
    mark_outbox_published,
)
from app.domain.policies.consent_sync_service import is_contact_actionable
from app.domain.runtime_settings import resolve_team_notification_email
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
)
from app.domain.shared_records import service as shared_record_service
from app.domain.voice.models import (
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain_models import Campaign, Contact, OutboxEvent
from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.registry import resolve_email_adapter
from app.infrastructure.providers.sendgrid import SendGridAdapter

router = APIRouter(
    prefix="/calls", tags=["calls"], dependencies=[Depends(require_admin)]
)


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


class TestCallCreate(SQLModel):
    """Request payload for queueing a manual voice test call."""

    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    voice_script_id: uuid.UUID
    scheduled_at: datetime | None = None


class TestCallPublic(SQLModel):
    """API response model: queued test call."""

    call_request_id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    voice_script_id: uuid.UUID
    status: str
    scheduled_at: datetime
    message: str


class CallOutcomeIntelligencePublic(SQLModel):
    """Derived call intelligence for post-call routing."""

    summary: str
    sentiment: str
    objection: str | None
    next_action: str
    recommended_follow_up: str


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
    intelligence: CallOutcomeIntelligencePublic | None = None


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


def _load_contact_for_workspace(
    _session: SessionDep,
    *,
    workspace_id: str,
    contact_id: uuid.UUID,
) -> Contact | None:
    shared_contact = shared_record_service.get_shared_contact(
        workspace_id=workspace_id,
        contact_id=contact_id,
    )
    if shared_contact is None:
        return None
    contact = shared_record_service.shared_contact_to_contact(shared_contact)
    if contact and contact.workspace_id != workspace_id:
        return None
    return contact


def _call_action_intent_key(call_request_id: uuid.UUID, action: str) -> str:
    return f"call_request:{call_request_id}:{action}"


def _provider_send_accepted(result: dict) -> bool:
    status_code = int(result.get("status_code") or 0)
    return 200 <= status_code < 300


def _extract_unanswered_questions(unanswered_questions: object) -> list[str]:
    if unanswered_questions is None:
        return []
    if isinstance(unanswered_questions, list):
        return [str(item).strip() for item in unanswered_questions if str(item).strip()]
    if isinstance(unanswered_questions, dict):
        raw_questions = (
            unanswered_questions.get("questions")
            or unanswered_questions.get("items")
            or unanswered_questions.get("unanswered")
            or []
        )
        if isinstance(raw_questions, list):
            return [str(item).strip() for item in raw_questions if str(item).strip()]
        if isinstance(raw_questions, str) and raw_questions.strip():
            return [raw_questions.strip()]
    if isinstance(unanswered_questions, str) and unanswered_questions.strip():
        return [unanswered_questions.strip()]
    return []


def _sentiment_from_transcript(transcript: str) -> str:
    text = transcript.lower()
    negative_terms = (
        "not interested",
        "no budget",
        "too expensive",
        "bad fit",
        "do not call",
        "stop calling",
        "declined",
    )
    positive_terms = (
        "interested",
        "book",
        "booking",
        "demo",
        "schedule",
        "yes",
        "great",
        "next tuesday",
    )
    if any(term in text for term in negative_terms):
        return "negative"
    if any(term in text for term in positive_terms):
        return "positive"
    return "neutral"


def _detect_objection(transcript: str, questions: list[str]) -> str | None:
    if questions:
        return questions[0]

    text = transcript.lower()
    if "pricing" in text or "price" in text:
        return "pricing clarity"
    if "budget" in text:
        return "budget concern"
    if "timing" in text or "later" in text:
        return "timing concern"
    if "authority" in text or "manager" in text or "approval" in text:
        return "approval needed"
    return None


def _summary_for_call(
    session: CallSession,
    *,
    transcript: str,
    objection: str | None,
) -> str:
    if session.scheduling_interest and objection:
        return f"Buyer showed interest and needs {objection}."
    if session.scheduling_interest:
        return "Buyer showed interest in scheduling a follow-up."
    if objection:
        return f"Call surfaced {objection}."
    if transcript:
        sentence = transcript.strip().split(".")[0].strip()
        return sentence[:220] if sentence else "Call completed with transcript."
    if session.outcome:
        return f"Call completed with outcome {session.outcome.value}."
    return "Call completed."


def _build_call_outcome_intelligence(
    session: CallSession | None,
) -> CallOutcomeIntelligencePublic | None:
    if session is None:
        return None

    transcript = (session.transcript or "").strip()
    questions = _extract_unanswered_questions(session.unanswered_questions)
    objection = _detect_objection(transcript, questions)
    sentiment = _sentiment_from_transcript(transcript)

    if (
        not transcript
        and not questions
        and not session.outcome
        and not session.scheduling_interest
    ):
        return None

    if session.scheduling_interest:
        next_action = "Book the requested meeting time."
    elif objection:
        next_action = f"Send a follow-up that addresses {objection}."
    elif session.outcome and session.outcome.value in {
        "voicemail",
        "no_answer",
        "busy",
    }:
        next_action = "Retry the call or send an email follow-up."
    else:
        next_action = "Send a recap and continue the sequence."

    if objection and session.scheduling_interest:
        recommended_follow_up = f"Send a follow-up that addresses {objection}, then confirm the meeting time."
    elif objection:
        recommended_follow_up = f"Lead with {objection} in the next outreach touch."
    elif session.outcome and session.outcome.value == "voicemail":
        recommended_follow_up = (
            "Send the voicemail recap by email and schedule a retry."
        )
    else:
        recommended_follow_up = (
            "Continue the sequence with a short recap and clear next step."
        )

    return CallOutcomeIntelligencePublic(
        summary=_summary_for_call(
            session,
            transcript=transcript,
            objection=objection,
        ),
        sentiment=sentiment,
        objection=objection,
        next_action=next_action,
        recommended_follow_up=recommended_follow_up,
    )


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
    workspace_id: str,
    call_request_id: uuid.UUID,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    action: str,
    event_type: str,
    event_data: dict,
) -> OutboxEvent | None:
    intent_key = _call_action_intent_key(call_request_id, action)
    existing = session.exec(
        select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.idempotency_key == intent_key,
        )
    ).first()
    if existing:
        if existing.published_at is not None:
            return None
        _raise_call_action_in_progress(action)

    return enqueue_outbox_event(
        session,
        workspace_id=workspace_id,
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


@router.post("/test-call", response_model=TestCallPublic)
def queue_test_call(
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    payload: TestCallCreate,
) -> TestCallPublic:
    """Queue a manual voice test call for the selected contact and script."""
    return _queue_test_call_once(
        session=session,
        current_user=current_user,
        workspace_id=workspace_id,
        payload=payload,
    )


def _queue_test_call_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    payload: TestCallCreate,
) -> TestCallPublic:
    campaign = session.get(Campaign, payload.campaign_id)
    if not campaign or campaign.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Campaign not found")

    contact = _load_contact_for_workspace(
        session,
        workspace_id=workspace_id,
        contact_id=payload.contact_id,
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if not contact.phone:
        raise HTTPException(status_code=400, detail="Contact phone is required")

    script = session.get(VoiceScript, payload.voice_script_id)
    if not script or script.campaign_id != campaign.id:
        raise HTTPException(status_code=404, detail="Voice script not found")
    if not script.active:
        raise HTTPException(status_code=400, detail="Voice script is inactive")

    scheduled_at = payload.scheduled_at or datetime.now(timezone.utc)
    call_request = CallRequest(
        workspace_id=workspace_id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_test_call",
        status=CallRequestStatus.queued,
        scheduled_at=scheduled_at,
    )
    session.add(call_request)
    session.flush()

    append_audit_event_to_session(
        session,
        event_name="call.test_call_queued",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="call_request",
        resource_id=str(call_request.id),
        payload={
            "call_request_id": str(call_request.id),
            "contact_id": str(contact.id),
            "campaign_id": str(campaign.id),
            "voice_script_id": str(script.id),
        },
    )
    session.commit()
    session.refresh(call_request)
    return TestCallPublic(
        call_request_id=call_request.id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        status=call_request.status.value,
        scheduled_at=call_request.scheduled_at,
        message="Test call queued",
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
            .where(
                Campaign.workspace_id == workspace_id, CallSession.outcome == outcome
            )
        )
        count_query = (
            select(func.count(CallRequest.id))
            .join(Campaign, CallRequest.campaign_id == Campaign.id)
            .join(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(
                Campaign.workspace_id == workspace_id, CallSession.outcome == outcome
            )
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
        unanswered_questions=(
            _extract_unanswered_questions(sess.unanswered_questions) if sess else None
        ),
        scheduling_interest=sess.scheduling_interest if sess else None,
        scheduled_at=req.scheduled_at,
        intelligence=_build_call_outcome_intelligence(sess),
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

    contact = _load_contact_for_workspace(
        session,
        workspace_id=workspace_id,
        contact_id=req.contact_id,
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    actionable, reason = is_contact_actionable(contact.model_dump(), "email")
    if not actionable:
        raise HTTPException(
            status_code=422,
            detail=f"Contact not actionable for email: {reason}",
        )

    name = contact.first_name or "there"
    intent = _prepare_call_action_intent(
        session,
        workspace_id=req.workspace_id,
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
        raise HTTPException(
            status_code=502, detail="Email provider rejected demo email"
        )

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
    mark_outbox_published(session, workspace_id=req.workspace_id, event_id=intent.id)
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

    contact = _load_contact_for_workspace(
        session,
        workspace_id=workspace_id,
        contact_id=req.contact_id,
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    team_email = resolve_team_notification_email(session, workspace_id)
    if not team_email:
        raise HTTPException(
            status_code=500, detail="Team notification email not configured"
        )

    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "Unknown"
    intent = _prepare_call_action_intent(
        session,
        workspace_id=req.workspace_id,
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
        raise HTTPException(
            status_code=502, detail="Email provider rejected sales flag"
        )

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
    mark_outbox_published(session, workspace_id=req.workspace_id, event_id=intent.id)
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
