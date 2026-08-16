"""Transactional lifecycle rules for commercial agent deployments."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDependency,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentLifecycleEvent,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)


class AgentRegistryError(ValueError):
    """Base class for deterministic registry validation failures."""


class AgentOwnershipError(AgentRegistryError):
    """A deployment references resources outside its tenant/workspace boundary."""


class AgentSlotLimitExceeded(AgentRegistryError):
    """The active contract has no remaining commercial agent slots."""


class AgentDependencyError(AgentRegistryError):
    """A required paid agent dependency is absent or unhealthy."""


class AgentLifecycleError(AgentRegistryError):
    """The requested deployment lifecycle transition is not allowed."""


_SLOT_CONSUMING_STATES = {
    AgentDeploymentStatus.VALIDATING.value,
    AgentDeploymentStatus.ACTIVE.value,
    AgentDeploymentStatus.SUSPENDED.value,
    AgentDeploymentStatus.DEGRADED.value,
}
_CHANNEL_AGENT_TYPES = {
    "email": AgentType.EMAIL_OUTREACH,
    "voice": AgentType.VOICE_CONVERSATION,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lock_tenant(session: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = session.exec(
        select(Tenant).where(Tenant.id == tenant_id).with_for_update()
    ).one_or_none()
    if tenant is None or tenant.status != "ACTIVE":
        raise AgentOwnershipError("tenant is not active")
    return tenant


def _load_owned_deployment(
    session: Session, *, tenant_id: uuid.UUID, deployment_id: uuid.UUID
) -> AgentDeployment:
    deployment = session.exec(
        select(AgentDeployment).where(
            AgentDeployment.id == deployment_id,
            AgentDeployment.tenant_id == tenant_id,
        )
    ).one_or_none()
    if deployment is None:
        raise AgentOwnershipError("agent deployment was not found for tenant")
    return deployment


def _validate_ownership(
    session: Session, *, tenant_id: uuid.UUID, deployment: AgentDeployment
) -> tuple[ProductInstallation, AgentCatalogDefinition, AgentPlanEntitlement]:
    installation = session.get(ProductInstallation, deployment.installation_id)
    if (
        installation is None
        or installation.tenant_id != tenant_id
        or ProductCode(installation.product_code) is not ProductCode.SIGNAL_LOOP
        or installation.status != "ACTIVE"
    ):
        raise AgentOwnershipError("active SignalLoop installation is required")

    binding = session.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.tenant_id == tenant_id,
            TenantWorkspaceBinding.installation_id == installation.id,
            TenantWorkspaceBinding.workspace_id == deployment.workspace_id,
            TenantWorkspaceBinding.status == "ACTIVE",
        )
    ).one_or_none()
    if binding is None or installation.local_identifier != deployment.workspace_id:
        raise AgentOwnershipError("active tenant workspace binding is required")

    catalog = session.get(AgentCatalogDefinition, deployment.catalog_definition_id)
    if (
        catalog is None
        or catalog.lifecycle_status != "PUBLISHED"
        or AgentType(catalog.agent_type) is not AgentType(deployment.agent_type)
    ):
        raise AgentOwnershipError("published matching catalog definition is required")

    now = _now()
    entitlements = session.exec(
        select(AgentPlanEntitlement).where(
            AgentPlanEntitlement.tenant_id == tenant_id,
            AgentPlanEntitlement.installation_id == installation.id,
            AgentPlanEntitlement.status == "ACTIVE",
        )
    ).all()
    eligible = [
        entitlement
        for entitlement in entitlements
        if _as_utc(entitlement.effective_from) <= now
        and (
            entitlement.effective_to is None or _as_utc(entitlement.effective_to) > now
        )
    ]
    if len(eligible) != 1:
        raise AgentOwnershipError(
            "exactly one active agent plan entitlement is required"
        )
    entitlement = eligible[0]
    if (
        entitlement.allowed_agent_types
        and AgentType(deployment.agent_type).value
        not in entitlement.allowed_agent_types
    ):
        raise AgentOwnershipError("agent type is not allowed by the active plan")
    return installation, catalog, entitlement


def _validate_slot_limit(
    session: Session,
    *,
    deployment: AgentDeployment,
    entitlement: AgentPlanEntitlement,
) -> None:
    occupied = session.exec(
        select(func.count(AgentDeployment.id)).where(
            AgentDeployment.tenant_id == deployment.tenant_id,
            AgentDeployment.id != deployment.id,
            AgentDeployment.status.in_(_SLOT_CONSUMING_STATES),
        )
    ).one()
    if int(occupied) >= entitlement.purchased_slots:
        raise AgentSlotLimitExceeded("purchased agent slot limit has been reached")

    ceiling = entitlement.type_ceilings.get(AgentType(deployment.agent_type).value)
    if ceiling is None:
        return
    same_type = session.exec(
        select(func.count(AgentDeployment.id)).where(
            AgentDeployment.tenant_id == deployment.tenant_id,
            AgentDeployment.id != deployment.id,
            AgentDeployment.agent_type == AgentType(deployment.agent_type),
            AgentDeployment.status.in_(_SLOT_CONSUMING_STATES),
        )
    ).one()
    if int(same_type) >= ceiling:
        raise AgentSlotLimitExceeded("agent type ceiling has been reached")


def _validate_dependencies(session: Session, deployment: AgentDeployment) -> None:
    edges = session.exec(
        select(AgentDependency).where(
            AgentDependency.tenant_id == deployment.tenant_id,
            AgentDependency.source_deployment_id == deployment.id,
            AgentDependency.status == "ACTIVE",
        )
    ).all()
    targets: dict[uuid.UUID, AgentDeployment] = {}
    for edge in edges:
        target = session.get(AgentDeployment, edge.target_deployment_id)
        if (
            target is None
            or target.tenant_id != deployment.tenant_id
            or target.workspace_id != deployment.workspace_id
            or target.status != AgentDeploymentStatus.ACTIVE
        ):
            raise AgentDependencyError("agent dependency is missing or inactive")
        target_catalog = session.get(
            AgentCatalogDefinition, target.catalog_definition_id
        )
        if target_catalog is None or (
            edge.minimum_catalog_version is not None
            and target_catalog.catalog_version < edge.minimum_catalog_version
        ):
            raise AgentDependencyError(
                "agent dependency catalog version is not eligible"
            )
        targets[target.id] = target

    if AgentType(deployment.agent_type) is not AgentType.CAMPAIGN_MANAGER:
        return
    channels = deployment.configuration.get("channels", [])
    if not isinstance(channels, list):
        raise AgentDependencyError("campaign manager channels must be a list")
    for raw_channel in channels:
        channel = str(raw_channel).strip().lower()
        required_type = _CHANNEL_AGENT_TYPES.get(channel)
        if required_type is None:
            raise AgentDependencyError("campaign manager channel is unsupported")
        if not any(
            AgentType(target.agent_type) is required_type for target in targets.values()
        ):
            raise AgentDependencyError(
                f"campaign manager requires an active paid {channel} agent dependency"
            )


def _record_lifecycle_event(
    session: Session,
    *,
    deployment: AgentDeployment,
    event_type: str,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
    reason: str | None = None,
) -> None:
    session.add(
        AgentLifecycleEvent(
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            event_type=event_type,
            lifecycle_version=deployment.lifecycle_version,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            payload={
                "agent_type": AgentType(deployment.agent_type).value,
                "catalog_definition_id": str(deployment.catalog_definition_id),
                "workspace_id": deployment.workspace_id,
                "status": AgentDeploymentStatus(deployment.status).value,
            },
        )
    )


def validate_deployment(
    session: Session, *, tenant_id: uuid.UUID, deployment_id: uuid.UUID
) -> AgentDeployment:
    """Validate current ownership, contract, slot, catalog, and dependencies."""

    deployment = _load_owned_deployment(
        session, tenant_id=tenant_id, deployment_id=deployment_id
    )
    _, _, entitlement = _validate_ownership(
        session, tenant_id=tenant_id, deployment=deployment
    )
    _validate_slot_limit(session, deployment=deployment, entitlement=entitlement)
    _validate_dependencies(session, deployment)
    return deployment


def activate_deployment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
) -> AgentDeployment:
    """Validate and activate one deployment while holding the tenant slot lock."""

    _lock_tenant(session, tenant_id)
    deployment = _load_owned_deployment(
        session, tenant_id=tenant_id, deployment_id=deployment_id
    )
    if deployment.status == AgentDeploymentStatus.ACTIVE:
        return deployment
    if deployment.status not in {
        AgentDeploymentStatus.DRAFT,
        AgentDeploymentStatus.VALIDATING,
        AgentDeploymentStatus.DEGRADED,
    }:
        raise AgentLifecycleError(
            "deployment cannot be activated from its current state"
        )

    _, _, entitlement = _validate_ownership(
        session, tenant_id=tenant_id, deployment=deployment
    )
    _validate_slot_limit(session, deployment=deployment, entitlement=entitlement)
    _validate_dependencies(session, deployment)

    now = _now()
    deployment.status = AgentDeploymentStatus.ACTIVE
    deployment.activated_at = now
    deployment.suspended_at = None
    deployment.lifecycle_version += 1
    deployment.updated_at = now
    session.add(deployment)
    _record_lifecycle_event(
        session,
        deployment=deployment,
        event_type="agent.deployment.activated",
        actor_id=actor_id,
        actor_role=actor_role,
    )
    session.flush()
    return deployment


def suspend_deployment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
    reason: str,
) -> AgentDeployment:
    """Suspend new work while preserving the deployment's purchased slot."""

    _lock_tenant(session, tenant_id)
    deployment = _load_owned_deployment(
        session, tenant_id=tenant_id, deployment_id=deployment_id
    )
    if deployment.status == AgentDeploymentStatus.SUSPENDED:
        return deployment
    if deployment.status not in {
        AgentDeploymentStatus.ACTIVE,
        AgentDeploymentStatus.DEGRADED,
    }:
        raise AgentLifecycleError(
            "deployment cannot be suspended from its current state"
        )
    if not reason.strip():
        raise AgentLifecycleError("suspension reason is required")

    now = _now()
    deployment.status = AgentDeploymentStatus.SUSPENDED
    deployment.suspended_at = now
    deployment.lifecycle_version += 1
    deployment.updated_at = now
    session.add(deployment)
    _record_lifecycle_event(
        session,
        deployment=deployment,
        event_type="agent.deployment.suspended",
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason.strip(),
    )
    session.flush()
    return deployment


def resume_deployment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
) -> AgentDeployment:
    """Resume a suspended deployment after revalidating its live contract."""

    _lock_tenant(session, tenant_id)
    deployment = _load_owned_deployment(
        session, tenant_id=tenant_id, deployment_id=deployment_id
    )
    if deployment.status == AgentDeploymentStatus.ACTIVE:
        return deployment
    if deployment.status != AgentDeploymentStatus.SUSPENDED:
        raise AgentLifecycleError("only a suspended deployment can be resumed")
    _, _, entitlement = _validate_ownership(
        session, tenant_id=tenant_id, deployment=deployment
    )
    _validate_slot_limit(session, deployment=deployment, entitlement=entitlement)
    _validate_dependencies(session, deployment)

    now = _now()
    deployment.status = AgentDeploymentStatus.ACTIVE
    deployment.suspended_at = None
    deployment.lifecycle_version += 1
    deployment.updated_at = now
    session.add(deployment)
    _record_lifecycle_event(
        session,
        deployment=deployment,
        event_type="agent.deployment.resumed",
        actor_id=actor_id,
        actor_role=actor_role,
    )
    session.flush()
    return deployment


def retire_deployment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
    reason: str,
) -> AgentDeployment:
    """Permanently retire a deployment and release its commercial slot."""

    _lock_tenant(session, tenant_id)
    deployment = _load_owned_deployment(
        session, tenant_id=tenant_id, deployment_id=deployment_id
    )
    if deployment.status == AgentDeploymentStatus.RETIRED:
        return deployment
    if not reason.strip():
        raise AgentLifecycleError("retirement reason is required")

    now = _now()
    deployment.status = AgentDeploymentStatus.RETIRED
    deployment.retired_at = now
    deployment.lifecycle_version += 1
    deployment.updated_at = now
    session.add(deployment)
    _record_lifecycle_event(
        session,
        deployment=deployment,
        event_type="agent.deployment.retired",
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason.strip(),
    )
    session.flush()
    return deployment
