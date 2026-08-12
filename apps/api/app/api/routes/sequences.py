"""FastAPI router: ``sequences`` endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.sequences import service as sequence_service
from app.domain.sequences.models import EmailSequence
from app.domain.sequences.schemas import (
    EnrollmentResult,
    SequenceCreate,
    SequenceDetailPublic,
    SequencePublic,
    SequencesPublic,
    SequenceUpdate,
    StepsBatchUpdate,
)
from app.domain_models import Campaign

router = APIRouter(prefix="/sequences", tags=["sequences"])


def _ensure_campaign_in_workspace(
    session: SessionDep,
    campaign_id: uuid.UUID,
    workspace_id: str,
) -> None:
    campaign = session.exec(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")


def _get_sequence_or_404(
    session: SessionDep,
    sequence_id: uuid.UUID,
    workspace_id: str,
) -> EmailSequence:
    sequence = session.exec(
        select(EmailSequence)
        .join(Campaign, EmailSequence.campaign_id == Campaign.id)
        .where(
            EmailSequence.id == sequence_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return sequence


@router.post("/", response_model=SequencePublic, dependencies=[Depends(require_admin)])
async def create_sequence(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    body: SequenceCreate,
) -> SequencePublic:
    """Create sequence."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="sequences.create",
        request_payload=body.model_dump(mode="json"),
        mutation=lambda: _create_sequence_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            body=body,
        ),
    )


def _create_sequence_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    body: SequenceCreate,
) -> SequencePublic:
    _ensure_campaign_in_workspace(session, body.campaign_id, workspace_id)
    seq = sequence_service.create_sequence(
        session, data=body, created_by=current_user.id, commit=False
    )
    append_audit_event_to_session(
        session,
        event_name="sequence.created",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="sequence",
        resource_id=str(seq.id),
        payload={"id": str(seq.id), "name": seq.name},
    )
    session.commit()
    session.refresh(seq)
    return SequencePublic(
        id=seq.id,
        campaign_id=seq.campaign_id,
        name=seq.name,
        active=seq.active,
        created_at=seq.created_at,
    )


@router.get("/", response_model=SequencesPublic)
def list_sequences(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID | None = None,
) -> SequencesPublic:
    """Return a list of sequences."""
    query = (
        select(EmailSequence)
        .join(Campaign, EmailSequence.campaign_id == Campaign.id)
        .where(Campaign.workspace_id == workspace_id)
    )
    if campaign_id:
        query = query.where(EmailSequence.campaign_id == campaign_id)
    sequences = session.exec(query.order_by(EmailSequence.created_at.desc())).all()
    return SequencesPublic(
        data=[
            SequencePublic(
                id=s.id,
                campaign_id=s.campaign_id,
                name=s.name,
                active=s.active,
                created_at=s.created_at,
            )
            for s in sequences
        ],
        count=len(sequences),
    )


@router.get("/{sequence_id}", response_model=SequenceDetailPublic)
def get_sequence(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
) -> SequenceDetailPublic:
    """Return sequence."""
    _get_sequence_or_404(session, sequence_id, workspace_id)
    return sequence_service.get_sequence_detail(session, sequence_id)


@router.put("/{sequence_id}", response_model=SequencePublic, dependencies=[Depends(require_admin)])
async def update_sequence(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
    body: SequenceUpdate,
) -> SequencePublic:
    """Update sequence."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="sequences.update",
        request_payload={
            "sequence_id": str(sequence_id),
            "body": body.model_dump(mode="json", exclude_unset=True),
        },
        mutation=lambda: _update_sequence_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            body=body,
        ),
    )


def _update_sequence_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    sequence_id: uuid.UUID,
    body: SequenceUpdate,
) -> SequencePublic:
    _get_sequence_or_404(session, sequence_id, workspace_id)
    seq = sequence_service.update_sequence(session, sequence_id=sequence_id, data=body, commit=False)
    append_audit_event_to_session(
        session,
        event_name="sequence.updated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="sequence",
        resource_id=str(seq.id),
        payload={"id": str(seq.id)},
    )
    session.commit()
    session.refresh(seq)
    return SequencePublic(
        id=seq.id,
        campaign_id=seq.campaign_id,
        name=seq.name,
        active=seq.active,
        created_at=seq.created_at,
    )


@router.put(
    "/{sequence_id}/steps",
    response_model=SequenceDetailPublic,
    dependencies=[Depends(require_admin)],
)
async def update_steps(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
    body: StepsBatchUpdate,
) -> SequenceDetailPublic:
    """Update steps."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="sequences.steps.update",
        request_payload={
            "sequence_id": str(sequence_id),
            "body": body.model_dump(mode="json"),
        },
        mutation=lambda: _update_steps_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            body=body,
        ),
    )


def _update_steps_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    sequence_id: uuid.UUID,
    body: StepsBatchUpdate,
) -> SequenceDetailPublic:
    _get_sequence_or_404(session, sequence_id, workspace_id)
    sequence_service.batch_upsert_steps(
        session, sequence_id=sequence_id, steps=body.steps, commit=False
    )
    append_audit_event_to_session(
        session,
        event_name="sequence.steps_updated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="sequence",
        resource_id=str(sequence_id),
        payload={"sequence_id": str(sequence_id), "step_count": len(body.steps)},
    )
    session.commit()
    return sequence_service.get_sequence_detail(session, sequence_id)


@router.delete("/{sequence_id}", dependencies=[Depends(require_admin)])
async def delete_sequence(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, str]:
    """Delete sequence."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="sequences.delete",
        request_payload={"sequence_id": str(sequence_id)},
        mutation=lambda: _delete_sequence_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            sequence_id=sequence_id,
        ),
    )


def _delete_sequence_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    sequence_id: uuid.UUID,
) -> dict[str, str]:
    _get_sequence_or_404(session, sequence_id, workspace_id)
    sequence_service.delete_sequence(session, sequence_id, commit=False)
    append_audit_event_to_session(
        session,
        event_name="sequence.deleted",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="sequence",
        resource_id=str(sequence_id),
        payload={"id": str(sequence_id)},
    )
    session.commit()
    return {"message": "Sequence deleted"}


@router.post(
    "/{sequence_id}/enroll/{campaign_id}",
    response_model=EnrollmentResult,
    dependencies=[Depends(require_admin)],
)
async def enroll_contacts(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    campaign_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> EnrollmentResult:
    """Enroll contacts."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="sequences.enroll",
        request_payload={
            "sequence_id": str(sequence_id),
            "campaign_id": str(campaign_id),
        },
        mutation=lambda: _enroll_contacts_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            sequence_id=sequence_id,
            campaign_id=campaign_id,
        ),
    )


def _enroll_contacts_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    sequence_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> EnrollmentResult:
    sequence = _get_sequence_or_404(session, sequence_id, workspace_id)
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    if sequence.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Sequence not found")
    enrolled = sequence_service.enroll_campaign_contacts(
        session, campaign_id=campaign_id, sequence_id=sequence_id, commit=False
    )
    append_audit_event_to_session(
        session,
        event_name="sequence.contacts_enrolled",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="sequence",
        resource_id=str(sequence_id),
        payload={
            "sequence_id": str(sequence_id),
            "campaign_id": str(campaign_id),
            "enrolled": enrolled,
        },
    )
    session.commit()
    return EnrollmentResult(enrolled=enrolled, message=f"Enrolled {enrolled} contacts")


@router.get("/{sequence_id}/progress")
def get_sequence_progress(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
) -> dict:
    """Get step-by-step progress breakdown for a sequence."""
    from sqlalchemy import func as sa_func

    from app.domain.sequences.models import (
        ContactSequenceState,
        SequenceStatus,
        SequenceStep,
    )

    sequence = _get_sequence_or_404(session, sequence_id, workspace_id)

    # Get steps
    steps = session.exec(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .order_by(SequenceStep.step_order)
    ).all()

    # Get contact state aggregates
    total = session.exec(
        select(sa_func.count(ContactSequenceState.id)).where(
            ContactSequenceState.sequence_id == sequence_id
        )
    ).one()

    status_counts = session.exec(
        select(
            ContactSequenceState.status,
            sa_func.count(ContactSequenceState.id),
        )
        .where(ContactSequenceState.sequence_id == sequence_id)
        .group_by(ContactSequenceState.status)
    ).all()

    # Step breakdown
    step_progress = session.exec(
        select(
            ContactSequenceState.current_step,
            sa_func.count(ContactSequenceState.id),
        )
        .where(
            ContactSequenceState.sequence_id == sequence_id,
            ContactSequenceState.status == SequenceStatus.active,
        )
        .group_by(ContactSequenceState.current_step)
    ).all()

    return {
        "sequence_id": str(sequence_id),
        "sequence_name": sequence.name,
        "total_steps": len(steps),
        "total_enrolled": total,
        "status_breakdown": {status.value if hasattr(status, 'value') else status: count for status, count in status_counts},
        "step_progress": [
            {"step": step, "active_contacts": count}
            for step, count in step_progress
        ],
    }


@router.get("/{sequence_id}/contacts")
def get_sequence_contacts(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    status: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Paginated list of contacts in a sequence with their states."""
    from sqlalchemy import func as sa_func

    from app.domain.sequences.models import ContactSequenceState

    _get_sequence_or_404(session, sequence_id, workspace_id)

    query = select(ContactSequenceState).where(
        ContactSequenceState.sequence_id == sequence_id
    )
    count_query = select(sa_func.count(ContactSequenceState.id)).where(
        ContactSequenceState.sequence_id == sequence_id
    )

    if status:
        query = query.where(ContactSequenceState.status == status)
        count_query = count_query.where(ContactSequenceState.status == status)

    total = session.exec(count_query).one()
    states = session.exec(query.offset(skip).limit(limit)).all()

    return {
        "data": [
            {
                "id": str(s.id),
                "contact_id": str(s.contact_id),
                "current_step": s.current_step,
                "status": s.status.value if hasattr(s.status, 'value') else s.status,
                "signal_type": s.signal_type,
                "next_send_at": s.next_send_at.isoformat() if s.next_send_at else None,
            }
            for s in states
        ],
        "count": total,
    }
