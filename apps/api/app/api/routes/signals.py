"""Signal event endpoints — aggregated cross-channel signals."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, select

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.signals import aggregation_service
from app.domain_models import Campaign, Contact

router = APIRouter(prefix="/signals", tags=["signals"], dependencies=[Depends(require_admin)])


class SignalPublic(SQLModel):
    """API response model: signal."""
    id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    channel: str
    signal_type: str
    confidence: float
    created_at: datetime


class SignalListPublic(SQLModel):
    """API response model: signal list."""
    data: list[SignalPublic]
    count: int


def _ensure_contact_in_workspace(
    session: SessionDep,
    contact_id: uuid.UUID,
    workspace_id: str,
) -> None:
    contact = session.exec(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.workspace_id == workspace_id,
        )
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")


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


@router.get("/contacts/{contact_id}", response_model=SignalListPublic)
def get_contact_signals(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    contact_id: uuid.UUID,
    channel: str | None = None,
    signal_type: str | None = None,
) -> SignalListPublic:
    """Return contact signals."""
    _ensure_contact_in_workspace(session, contact_id, workspace_id)
    signals = aggregation_service.get_contact_signals(
        session, contact_id, channel=channel, signal_type=signal_type
    )
    return SignalListPublic(
        data=[
            SignalPublic(
                id=s.id,
                contact_id=s.contact_id,
                campaign_id=s.campaign_id,
                channel=s.channel,
                signal_type=s.signal_type,
                confidence=s.confidence,
                created_at=s.created_at,
            )
            for s in signals
        ],
        count=len(signals),
    )


@router.get("/campaigns/{campaign_id}/summary")
def get_campaign_signal_summary(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID,
) -> dict:
    """Return campaign signal summary."""
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    return aggregation_service.get_campaign_signal_summary(session, campaign_id)
