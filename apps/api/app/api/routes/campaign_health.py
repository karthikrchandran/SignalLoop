"""Campaign health and dead-letter visibility endpoints (Story 5.3)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.config import settings
from app.core.idempotency import run_idempotent_mutation
from app.domain.outreach.action_queue_service import _now
from app.domain_models import (
    ActionQueue,
    Campaign,
    CampaignHealthPublic,
    DeadLetterEvent,
    DeadLetterItemPublic,
    DeadLetterListPublic,
    RoutingDecision,
)

router = APIRouter(prefix="/campaigns", tags=["campaign-health"])

_HEALTH_CACHE_TTL = 30  # seconds


def _health_cache_key(campaign_id: uuid.UUID, workspace_id: str = "") -> str:
    return f"campaign_health:{workspace_id}:{campaign_id.hex}"


def _ensure_campaign_in_workspace(
    session: Session,
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


async def _get_cached_health(request: Request, key: str) -> CampaignHealthPublic | None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return None
        raw = await redis.get(key)
        if raw:
            return CampaignHealthPublic(**json.loads(raw))
    except Exception:  # noqa: BLE001
        pass
    return None


async def _cache_health(
    request: Request, key: str, health: CampaignHealthPublic
) -> None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return
        await redis.setex(
            key, _HEALTH_CACHE_TTL, json.dumps(health.model_dump(), default=str)
        )
    except Exception:  # noqa: BLE001
        pass


def _compute_health(
    session: Session, campaign_id: uuid.UUID, workspace_id: str
) -> CampaignHealthPublic:
    now = _now()
    one_hour_ago = now - timedelta(hours=1)
    twenty_four_hours_ago = now - timedelta(hours=24)

    # Active count: pending items in action_queue for this campaign
    active_count = session.exec(
        select(func.count(ActionQueue.id)).where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "pending",
        )
    ).one()

    # Dead-letter count: items currently in dead_letter status
    dead_letter_count = session.exec(
        select(func.count(ActionQueue.id)).where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "dead_letter",
        )
    ).one()

    # Success / failure counts from action_queue (last 1h and 24h)
    success_count_1h = session.exec(
        select(func.count(ActionQueue.id)).where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "completed",
            ActionQueue.executed_at >= one_hour_ago,
        )
    ).one()
    success_count_24h = session.exec(
        select(func.count(ActionQueue.id)).where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "completed",
            ActionQueue.executed_at >= twenty_four_hours_ago,
        )
    ).one()
    failure_count_24h = session.exec(
        select(func.count(ActionQueue.id)).where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status.in_(["failed", "dead_letter"]),
            ActionQueue.created_at >= twenty_four_hours_ago,
        )
    ).one()

    # Provider errors by type from routing_decisions (last 24h, reason_code grouping)
    provider_rows = session.exec(
        select(RoutingDecision.reason_code, func.count(RoutingDecision.id))
        .where(
            RoutingDecision.campaign_id == campaign_id,
            RoutingDecision.workspace_id == workspace_id,
            RoutingDecision.outcome == "failed",
            RoutingDecision.created_at >= twenty_four_hours_ago,
        )
        .group_by(RoutingDecision.reason_code)
    ).all()
    provider_errors_by_type: dict[str, int] = {
        (code or "UNKNOWN"): count for code, count in provider_rows
    }

    return CampaignHealthPublic(
        active_count=active_count,
        success_count_1h=success_count_1h,
        success_count_24h=success_count_24h,
        failure_count_24h=failure_count_24h,
        dead_letter_count=dead_letter_count,
        provider_errors_by_type=provider_errors_by_type,
    )


@router.get(
    "/{campaign_id}/health",
    response_model=CampaignHealthPublic,
    dependencies=[Depends(require_admin)],
)
async def get_campaign_health(
    campaign_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _current_user: CurrentUser,
) -> CampaignHealthPublic:
    """Return a live health snapshot for a campaign (Redis-cached 30 s, NFR8)."""
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    cache_key = _health_cache_key(campaign_id, workspace_id)
    cached = await _get_cached_health(request, cache_key)
    if cached is not None:
        return cached

    health = _compute_health(session, campaign_id, workspace_id)
    await _cache_health(request, cache_key, health)
    return health


@router.get(
    "/{campaign_id}/dead-letters",
    response_model=DeadLetterListPublic,
    dependencies=[Depends(require_admin)],
)
def list_dead_letters(
    campaign_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> DeadLetterListPublic:
    """List dead-letter queue items for a campaign (paginated)."""
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    offset = (page - 1) * limit

    total = session.exec(
        select(func.count(ActionQueue.id)).where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "dead_letter",
        )
    ).one()

    rows = session.exec(
        select(ActionQueue)
        .where(
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "dead_letter",
        )
        .order_by(ActionQueue.dead_lettered_at)
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        DeadLetterItemPublic(
            id=row.id,
            contact_id=row.contact_id,
            action_type=row.action_type,
            failure_reason=row.failure_reason,
            retry_count=row.retry_count,
            first_failed_at=row.dead_lettered_at or row.created_at,
            retry_eligible=row.retry_count < settings.MAX_RETRY_COUNT,
        )
        for row in rows
    ]

    return DeadLetterListPublic(data=items, count=total, page=page)


@router.post(
    "/{campaign_id}/dead-letters/{item_id}/retry",
    response_model=DeadLetterItemPublic,
    dependencies=[Depends(require_admin)],
)
async def retry_dead_letter(
    campaign_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKeyDep,
) -> DeadLetterItemPublic:
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="dead-letter-retry",
        request_payload={"campaign_id": str(campaign_id), "item_id": str(item_id)},
        mutation=lambda: _retry_dead_letter_once(
            campaign_id, item_id, request, session, workspace_id, current_user
        ),
    )


async def _retry_dead_letter_once(
    campaign_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: str,
    current_user: CurrentUser,
) -> DeadLetterItemPublic:
    """Re-queue a dead-letter item (validates retry eligibility)."""
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    action = session.exec(
        select(ActionQueue).where(
            ActionQueue.id == item_id,
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "dead_letter",
        )
    ).first()
    if action is None:
        raise HTTPException(status_code=404, detail="Dead-letter item not found")

    if action.retry_count >= settings.MAX_RETRY_COUNT:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "RETRY_INELIGIBLE",
                    "message": f"Max retry count ({settings.MAX_RETRY_COUNT}) exceeded",
                    "semantic": "POLICY_VIOLATION",
                }
            },
        )

    # Re-queue with fresh retry counter reset
    now = _now()
    action.status = "pending"
    action.retry_count = 0
    action.failure_reason = None
    action.dead_lettered_at = None
    action.next_retry_at = None
    session.add(action)

    # Attribution event
    dle = DeadLetterEvent(
        action_queue_id=action.id,
        campaign_id=action.campaign_id,
        contact_id=action.contact_id,
        workspace_id=workspace_id,
        action_type=action.action_type,
        failure_reason=None,
        event_type="retried",
        operator_id=current_user.id,
        created_at=now,
    )
    session.add(dle)
    session.commit()
    session.refresh(action)

    # Invalidate health cache
    try:
        redis = request.app.state.redis_manager.client
        if redis is not None:
            await redis.delete(_health_cache_key(campaign_id, workspace_id))
    except Exception:  # noqa: BLE001
        pass

    return DeadLetterItemPublic(
        id=action.id,
        contact_id=action.contact_id,
        action_type=action.action_type,
        failure_reason=action.failure_reason,
        retry_count=action.retry_count,
        first_failed_at=action.created_at,
        retry_eligible=True,
    )


@router.post(
    "/{campaign_id}/dead-letters/{item_id}/dismiss",
    response_model=DeadLetterItemPublic,
    dependencies=[Depends(require_admin)],
)
async def dismiss_dead_letter(
    campaign_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    idempotency_key: IdempotencyKeyDep,
) -> DeadLetterItemPublic:
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="dead-letter-dismiss",
        request_payload={"campaign_id": str(campaign_id), "item_id": str(item_id)},
        mutation=lambda: _dismiss_dead_letter_once(
            campaign_id, item_id, request, session, workspace_id, current_user
        ),
    )


async def _dismiss_dead_letter_once(
    campaign_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: str,
    current_user: CurrentUser,
) -> DeadLetterItemPublic:
    """Dismiss a dead-letter item (clears from queue with operator attribution)."""
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    action = session.exec(
        select(ActionQueue).where(
            ActionQueue.id == item_id,
            ActionQueue.campaign_id == campaign_id,
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.status == "dead_letter",
        )
    ).first()
    if action is None:
        raise HTTPException(status_code=404, detail="Dead-letter item not found")

    now = _now()
    action.status = "dismissed"
    session.add(action)

    dle = DeadLetterEvent(
        action_queue_id=action.id,
        campaign_id=action.campaign_id,
        contact_id=action.contact_id,
        workspace_id=workspace_id,
        action_type=action.action_type,
        failure_reason=action.failure_reason,
        event_type="dismissed",
        operator_id=current_user.id,
        created_at=now,
    )
    session.add(dle)
    session.commit()
    session.refresh(action)

    # Invalidate health cache
    try:
        redis = request.app.state.redis_manager.client
        if redis is not None:
            await redis.delete(_health_cache_key(campaign_id, workspace_id))
    except Exception:  # noqa: BLE001
        pass

    return DeadLetterItemPublic(
        id=action.id,
        contact_id=action.contact_id,
        action_type=action.action_type,
        failure_reason=action.failure_reason,
        retry_count=action.retry_count,
        first_failed_at=action.dead_lettered_at or action.created_at,
        retry_eligible=False,
    )
