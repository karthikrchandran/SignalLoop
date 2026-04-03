"""Campaign dashboard metrics endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.domain.dashboard import service as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/campaigns/{campaign_id}/email-metrics")
def get_email_metrics(session: SessionDep, campaign_id: uuid.UUID) -> dict:
    return dashboard_service.get_email_metrics(session, campaign_id)


@router.get("/campaigns/{campaign_id}/call-metrics")
def get_call_metrics(session: SessionDep, campaign_id: uuid.UUID) -> dict:
    return dashboard_service.get_call_metrics(session, campaign_id)


@router.get("/campaigns/{campaign_id}/signals")
def get_signal_summary(session: SessionDep, campaign_id: uuid.UUID) -> dict:
    return dashboard_service.get_signal_summary(session, campaign_id)


@router.get("/daily-cap-status")
def get_daily_cap_status(session: SessionDep) -> dict:
    return dashboard_service.get_daily_cap_status(session)
