"""Durable, idempotent capacity accounting for commercial agent deployments."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import Session, func, select

from app.domain.commercial_agents.models import (
    AgentCapacityOverride,
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentLifecycleEvent,
    AgentPlanEntitlement,
    AgentUsageLedger,
    AgentUsageState,
)


class AgentCapacityError(ValueError):
    """Base class for deterministic capacity-accounting failures."""


class AgentCapacityExceeded(AgentCapacityError):
    """The deployment has no remaining capacity for its billing day."""


class AgentCapacityOwnershipError(AgentCapacityError):
    """Capacity work is outside the deployment tenant/workspace boundary."""


class AgentCapacityStateError(AgentCapacityError):
    """The requested reservation transition is not allowed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lock_deployment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    deployment_id: uuid.UUID,
) -> AgentDeployment:
    deployment = session.exec(
        select(AgentDeployment)
        .where(
            AgentDeployment.id == deployment_id,
            AgentDeployment.tenant_id == tenant_id,
            AgentDeployment.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if deployment is None or deployment.status != AgentDeploymentStatus.ACTIVE:
        raise AgentCapacityOwnershipError("active owned agent deployment is required")
    return deployment


def _active_plan(
    session: Session, deployment: AgentDeployment, at: datetime
) -> AgentPlanEntitlement:
    plans = session.exec(
        select(AgentPlanEntitlement).where(
            AgentPlanEntitlement.tenant_id == deployment.tenant_id,
            AgentPlanEntitlement.installation_id == deployment.installation_id,
            AgentPlanEntitlement.status == "ACTIVE",
        )
    ).all()
    eligible = [
        plan
        for plan in plans
        if _as_utc(plan.effective_from) <= at
        and (plan.effective_to is None or _as_utc(plan.effective_to) > at)
    ]
    if len(eligible) != 1:
        raise AgentCapacityOwnershipError("exactly one active agent plan is required")
    return eligible[0]


def _billing_day(plan: AgentPlanEntitlement, at: datetime) -> date:
    try:
        local = at.astimezone(ZoneInfo(plan.billing_timezone))
    except ZoneInfoNotFoundError as exc:
        raise AgentCapacityOwnershipError("billing timezone is invalid") from exc
    shifted = local - timedelta(hours=plan.billing_day_start_hour)
    return shifted.date()


def _capacity_limit(
    session: Session,
    *,
    deployment: AgentDeployment,
    capacity_metric: str,
    at: datetime,
) -> int:
    catalog = session.get(AgentCatalogDefinition, deployment.catalog_definition_id)
    if catalog is None or catalog.default_capacity_metric != capacity_metric:
        raise AgentCapacityOwnershipError(
            "capacity metric does not match deployment catalog"
        )
    overrides = session.exec(
        select(AgentCapacityOverride)
        .where(
            AgentCapacityOverride.tenant_id == deployment.tenant_id,
            AgentCapacityOverride.deployment_id == deployment.id,
            AgentCapacityOverride.capacity_metric == capacity_metric,
        )
        .order_by(AgentCapacityOverride.effective_from.desc())
    ).all()
    for override in overrides:
        if _as_utc(override.effective_from) <= at and (
            override.effective_to is None or _as_utc(override.effective_to) > at
        ):
            return override.capacity_amount
    return catalog.default_capacity_amount


def reserve_capacity(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    deployment_id: uuid.UUID,
    capacity_metric: str,
    idempotency_key: str,
    units: int = 1,
    now: datetime | None = None,
) -> AgentUsageLedger:
    """Reserve units once while serializing against the deployment capacity row."""

    if units < 1 or not idempotency_key.strip():
        raise AgentCapacityError("positive units and idempotency key are required")
    at = _as_utc(now or _now())
    deployment = _lock_deployment(
        session,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        deployment_id=deployment_id,
    )
    existing = session.exec(
        select(AgentUsageLedger).where(
            AgentUsageLedger.deployment_id == deployment.id,
            AgentUsageLedger.capacity_metric == capacity_metric,
            AgentUsageLedger.idempotency_key == idempotency_key.strip(),
        )
    ).one_or_none()
    if existing is not None:
        if (
            existing.tenant_id != tenant_id
            or existing.workspace_id != workspace_id
            or existing.reserved_units != units
        ):
            raise AgentCapacityOwnershipError("capacity idempotency key conflicts")
        return existing

    plan = _active_plan(session, deployment, at)
    billing_day = _billing_day(plan, at)
    limit = _capacity_limit(
        session, deployment=deployment, capacity_metric=capacity_metric, at=at
    )
    occupied = session.exec(
        select(func.coalesce(func.sum(AgentUsageLedger.reserved_units), 0)).where(
            AgentUsageLedger.deployment_id == deployment.id,
            AgentUsageLedger.billing_day == billing_day,
            AgentUsageLedger.capacity_metric == capacity_metric,
            AgentUsageLedger.state.in_(
                [
                    AgentUsageState.RESERVED.value,
                    AgentUsageState.FINALIZED.value,
                    AgentUsageState.UNKNOWN.value,
                ]
            ),
        )
    ).one()
    if int(occupied) + units > limit:
        raise AgentCapacityExceeded("agent deployment daily capacity has been reached")

    reservation = AgentUsageLedger(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        deployment_id=deployment.id,
        billing_day=billing_day,
        capacity_metric=capacity_metric,
        idempotency_key=idempotency_key.strip(),
        state=AgentUsageState.RESERVED,
        reserved_units=units,
        created_at=at,
        updated_at=at,
    )
    session.add(reservation)
    session.flush()
    return reservation


def _lock_reservation(session: Session, reservation_id: uuid.UUID) -> AgentUsageLedger:
    reservation = session.exec(
        select(AgentUsageLedger)
        .where(AgentUsageLedger.id == reservation_id)
        .with_for_update()
    ).one_or_none()
    if reservation is None:
        raise AgentCapacityOwnershipError("capacity reservation was not found")
    return reservation


def finalize_capacity(
    session: Session,
    *,
    reservation_id: uuid.UUID,
    provider_receipt_id: str,
    finalized_units: int,
    provider_units: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> AgentUsageLedger:
    """Finalize a safe provider-accepted usage reservation exactly once."""

    if not provider_receipt_id.strip() or finalized_units < 1:
        raise AgentCapacityStateError(
            "provider receipt and positive finalized units are required"
        )
    reservation = _lock_reservation(session, reservation_id)
    if reservation.state == AgentUsageState.FINALIZED:
        if (
            reservation.provider_receipt_id != provider_receipt_id.strip()
            or reservation.finalized_units != finalized_units
        ):
            raise AgentCapacityStateError(
                "capacity finalization conflicts with stored receipt"
            )
        return reservation
    if reservation.state != AgentUsageState.RESERVED:
        raise AgentCapacityStateError("only reserved capacity can be finalized")
    if finalized_units > reservation.reserved_units:
        raise AgentCapacityStateError("finalized units exceed reserved units")

    reservation.state = AgentUsageState.FINALIZED
    reservation.finalized_units = finalized_units
    reservation.provider_receipt_id = provider_receipt_id.strip()
    reservation.provider_units = provider_units or {}
    reservation.failure_reason = None
    reservation.updated_at = _as_utc(now or _now())
    session.add(reservation)
    session.flush()
    return reservation


def release_capacity(
    session: Session,
    *,
    reservation_id: uuid.UUID,
    reason: str,
    now: datetime | None = None,
) -> AgentUsageLedger:
    """Release a reservation only when no external side effect was attempted."""

    reservation = _lock_reservation(session, reservation_id)
    if reservation.state == AgentUsageState.RELEASED:
        return reservation
    if reservation.state != AgentUsageState.RESERVED or not reason.strip():
        raise AgentCapacityStateError(
            "only reserved capacity with a reason can be released"
        )
    reservation.state = AgentUsageState.RELEASED
    reservation.failure_reason = reason.strip()
    reservation.updated_at = _as_utc(now or _now())
    session.add(reservation)
    session.flush()
    return reservation


def mark_capacity_unknown(
    session: Session,
    *,
    reservation_id: uuid.UUID,
    reason: str,
    now: datetime | None = None,
) -> AgentUsageLedger:
    """Hold capacity when an invoked provider may have accepted the work."""

    reservation = _lock_reservation(session, reservation_id)
    if reservation.state == AgentUsageState.UNKNOWN:
        return reservation
    if reservation.state != AgentUsageState.RESERVED or not reason.strip():
        raise AgentCapacityStateError("only reserved capacity can become unknown")
    reservation.state = AgentUsageState.UNKNOWN
    reservation.failure_reason = reason.strip()
    reservation.updated_at = _as_utc(now or _now())
    session.add(reservation)
    session.flush()
    return reservation


def reconcile_unknown_capacity(
    session: Session,
    *,
    reservation_id: uuid.UUID,
    accepted: bool,
    provider_receipt_id: str,
    actor_id: uuid.UUID,
    actor_role: str,
    reason: str,
    now: datetime | None = None,
) -> AgentUsageLedger:
    """Resolve unknown usage with durable provider evidence and operator audit."""

    if not provider_receipt_id.strip() or not reason.strip() or not actor_role.strip():
        raise AgentCapacityStateError(
            "receipt, actor role, and reconciliation reason are required"
        )
    reservation = _lock_reservation(session, reservation_id)
    if reservation.state != AgentUsageState.UNKNOWN:
        raise AgentCapacityStateError("only unknown capacity can be reconciled")
    at = _as_utc(now or _now())
    reservation.state = (
        AgentUsageState.FINALIZED if accepted else AgentUsageState.RELEASED
    )
    reservation.finalized_units = reservation.reserved_units if accepted else 0
    reservation.provider_receipt_id = provider_receipt_id.strip()
    reservation.failure_reason = reason.strip()
    reservation.updated_at = at
    session.add(reservation)
    deployment = session.get(AgentDeployment, reservation.deployment_id)
    if deployment is None or deployment.tenant_id != reservation.tenant_id:
        raise AgentCapacityOwnershipError("reservation deployment ownership is invalid")
    session.add(
        AgentLifecycleEvent(
            tenant_id=reservation.tenant_id,
            deployment_id=reservation.deployment_id,
            event_type="agent.capacity.reconciled",
            lifecycle_version=deployment.lifecycle_version,
            actor_id=actor_id,
            actor_role=actor_role.strip(),
            reason=reason.strip(),
            payload={
                "accepted": accepted,
                "capacity_metric": reservation.capacity_metric,
                "provider_receipt_id": provider_receipt_id.strip(),
                "reservation_id": str(reservation.id),
            },
            recorded_at=at,
        )
    )
    session.flush()
    return reservation
