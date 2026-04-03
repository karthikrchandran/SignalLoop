"""Signal event endpoints — aggregated cross-channel signals."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from sqlmodel import SQLModel

from app.api.deps import SessionDep
from app.domain.signals import aggregation_service
from app.domain.signals.models import SignalEvent

router = APIRouter(prefix="/signals", tags=["signals"])


class SignalPublic(SQLModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID
    channel: str
    signal_type: str
    confidence: float
    created_at: datetime


class SignalListPublic(SQLModel):
    data: list[SignalPublic]
    count: int


@router.get("/contacts/{contact_id}", response_model=SignalListPublic)
def get_contact_signals(
    session: SessionDep,
    contact_id: uuid.UUID,
    channel: str | None = None,
    signal_type: str | None = None,
) -> SignalListPublic:
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
    campaign_id: uuid.UUID,
) -> dict:
    return aggregation_service.get_campaign_signal_summary(session, campaign_id)
