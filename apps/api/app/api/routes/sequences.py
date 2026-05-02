from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.audit_events import append_audit_event
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
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: SequenceCreate,
) -> SequencePublic:
    _ensure_campaign_in_workspace(session, body.campaign_id, workspace_id)
    seq = sequence_service.create_sequence(
        session, data=body, created_by=current_user.id
    )
    await append_audit_event(
        event_name="sequence.created",
        workspace_id=workspace_id,
        payload={"id": str(seq.id), "name": seq.name},
    )
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
    _get_sequence_or_404(session, sequence_id, workspace_id)
    return sequence_service.get_sequence_detail(session, sequence_id)


@router.put("/{sequence_id}", response_model=SequencePublic, dependencies=[Depends(require_admin)])
async def update_sequence(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    body: SequenceUpdate,
) -> SequencePublic:
    _get_sequence_or_404(session, sequence_id, workspace_id)
    seq = sequence_service.update_sequence(session, sequence_id=sequence_id, data=body)
    await append_audit_event(
        event_name="sequence.updated",
        workspace_id=workspace_id,
        payload={"id": str(seq.id)},
    )
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
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    body: StepsBatchUpdate,
) -> SequenceDetailPublic:
    _get_sequence_or_404(session, sequence_id, workspace_id)
    sequence_service.batch_upsert_steps(
        session, sequence_id=sequence_id, steps=body.steps
    )
    await append_audit_event(
        event_name="sequence.steps_updated",
        workspace_id=workspace_id,
        payload={"sequence_id": str(sequence_id), "step_count": len(body.steps)},
    )
    return sequence_service.get_sequence_detail(session, sequence_id)


@router.delete("/{sequence_id}", dependencies=[Depends(require_admin)])
async def delete_sequence(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
) -> dict[str, str]:
    _get_sequence_or_404(session, sequence_id, workspace_id)
    sequence_service.delete_sequence(session, sequence_id)
    await append_audit_event(
        event_name="sequence.deleted",
        workspace_id=workspace_id,
        payload={"id": str(sequence_id)},
    )
    return {"message": "Sequence deleted"}


@router.post(
    "/{sequence_id}/enroll/{campaign_id}",
    response_model=EnrollmentResult,
    dependencies=[Depends(require_admin)],
)
async def enroll_contacts(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    sequence_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> EnrollmentResult:
    sequence = _get_sequence_or_404(session, sequence_id, workspace_id)
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    if sequence.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Sequence not found")
    enrolled = sequence_service.enroll_campaign_contacts(
        session, campaign_id=campaign_id, sequence_id=sequence_id
    )
    await append_audit_event(
        event_name="sequence.contacts_enrolled",
        workspace_id=workspace_id,
        payload={
            "sequence_id": str(sequence_id),
            "campaign_id": str(campaign_id),
            "enrolled": enrolled,
        },
    )
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
