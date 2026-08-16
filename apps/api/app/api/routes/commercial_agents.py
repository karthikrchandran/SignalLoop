"""Tenant-scoped administration for commercial SignalLoop agent deployments."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import IdempotencyKeyDep
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.commercial_agents.schemas import (
    AgentCatalogPublic,
    AgentDeploymentCreate,
    AgentDeploymentPublic,
    AgentEntitlementChange,
    AgentEntitlementPublic,
    AgentLifecycleReason,
)
from app.domain.commercial_agents.service import (
    AgentRegistryError,
    activate_deployment,
    resume_deployment,
    retire_deployment,
    suspend_deployment,
    validate_deployment,
)
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)

router = APIRouter(prefix="/commercial-agents", tags=["commercial-agents"])


def _authorize_agent_admin(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID
) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if user.is_superuser:
        return tenant
    try:
        context = resolve_suite_context(session, user_id=user.id, tenant_id=tenant_id)
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="Agent administration is required"
        ) from exc
    if "agents.admin.manage" not in context.capabilities:
        raise HTTPException(status_code=403, detail="Agent administration is required")
    return tenant


def _deployment_public(deployment: AgentDeployment) -> dict[str, Any]:
    return AgentDeploymentPublic.model_validate(deployment).model_dump(mode="json")


def _configuration_digest(configuration: dict[str, Any]) -> str:
    canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.get("/catalog", response_model=list[AgentCatalogPublic])
def list_catalog(
    *, session: SessionDep, user: CurrentUser
) -> list[AgentCatalogDefinition]:
    del user
    return list(
        session.exec(
            select(AgentCatalogDefinition)
            .where(AgentCatalogDefinition.lifecycle_status == "PUBLISHED")
            .order_by(
                AgentCatalogDefinition.agent_type,
                AgentCatalogDefinition.catalog_version,
            )
        ).all()
    )


@router.get("/tenants/{tenant_id}/entitlement", response_model=AgentEntitlementPublic)
def get_entitlement(
    *, session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID
) -> AgentPlanEntitlement:
    _authorize_agent_admin(session, user, tenant_id)
    entitlement = session.exec(
        select(AgentPlanEntitlement).where(
            AgentPlanEntitlement.tenant_id == tenant_id,
            AgentPlanEntitlement.status == "ACTIVE",
        )
    ).one_or_none()
    if entitlement is None:
        raise HTTPException(
            status_code=404, detail="Active agent entitlement not found"
        )
    return entitlement


@router.put("/tenants/{tenant_id}/entitlement", response_model=AgentEntitlementPublic)
async def provision_entitlement(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: AgentEntitlementChange,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Platform administration is required"
        )
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="commercial-agent:entitlement",
        request_payload=payload.model_dump(mode="json"),
        mutation=lambda: _provision_entitlement_once(
            session=session,
            user=user,
            tenant=tenant,
            payload=payload,
        ),
        safe_to_retry_on_failure=True,
    )


def _provision_entitlement_once(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant: Tenant,
    payload: AgentEntitlementChange,
) -> dict[str, Any]:
    session.exec(select(Tenant).where(Tenant.id == tenant.id).with_for_update()).one()
    installation = session.exec(
        select(ProductInstallation).where(
            ProductInstallation.id == payload.installation_id,
            ProductInstallation.tenant_id == tenant.id,
            ProductInstallation.product_code == ProductCode.SIGNAL_LOOP,
        )
    ).one_or_none()
    if installation is None:
        raise HTTPException(status_code=404, detail="SignalLoop installation not found")
    existing_contract = session.exec(
        select(AgentPlanEntitlement).where(
            AgentPlanEntitlement.tenant_id == tenant.id,
            AgentPlanEntitlement.installation_id == installation.id,
            AgentPlanEntitlement.contract_version == payload.contract_version,
        )
    ).one_or_none()
    if existing_contract is not None:
        raise HTTPException(
            status_code=409, detail="Agent contract version already exists"
        )
    previous = session.exec(
        select(AgentPlanEntitlement).where(
            AgentPlanEntitlement.tenant_id == tenant.id,
            AgentPlanEntitlement.installation_id == installation.id,
            AgentPlanEntitlement.status == "ACTIVE",
        )
    ).all()
    for prior in previous:
        prior.status = "SUPERSEDED"
        session.add(prior)
    entitlement = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code=payload.plan_code,
        contract_version=payload.contract_version,
        purchased_slots=payload.purchased_slots,
        allowed_agent_types=[item.value for item in payload.allowed_agent_types],
        type_ceilings={
            item.value: limit for item, limit in payload.type_ceilings.items()
        },
        billing_timezone=payload.billing_timezone,
        billing_day_start_hour=payload.billing_day_start_hour,
        contract_reference=payload.contract_reference,
        approved_by=user.id,
    )
    session.add(entitlement)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="agent.entitlement.provisioned",
        workspace_id=str(tenant.id),
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="agent_plan_entitlement",
        resource_id=str(entitlement.id),
        payload={
            "contract_version": entitlement.contract_version,
            "installation_id": str(installation.id),
            "plan_code": entitlement.plan_code,
            "purchased_slots": entitlement.purchased_slots,
        },
    )
    return AgentEntitlementPublic.model_validate(entitlement).model_dump(mode="json")


@router.get(
    "/tenants/{tenant_id}/deployments", response_model=list[AgentDeploymentPublic]
)
def list_deployments(
    *, session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID
) -> list[AgentDeployment]:
    _authorize_agent_admin(session, user, tenant_id)
    return list(
        session.exec(
            select(AgentDeployment)
            .where(AgentDeployment.tenant_id == tenant_id)
            .order_by(AgentDeployment.created_at)
        ).all()
    )


@router.post(
    "/tenants/{tenant_id}/deployments",
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: AgentDeploymentCreate,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation="commercial-agent:create",
        request_payload=payload.model_dump(mode="json"),
        mutation=lambda: _create_deployment_once(
            session=session,
            user=user,
            tenant_id=tenant_id,
            payload=payload,
        ),
        safe_to_retry_on_failure=True,
    )


def _create_deployment_once(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: AgentDeploymentCreate,
) -> dict[str, Any]:
    session.exec(select(Tenant).where(Tenant.id == tenant_id).with_for_update()).one()
    installation = session.exec(
        select(ProductInstallation).where(
            ProductInstallation.id == payload.installation_id,
            ProductInstallation.tenant_id == tenant_id,
            ProductInstallation.product_code == ProductCode.SIGNAL_LOOP,
            ProductInstallation.status == "ACTIVE",
        )
    ).one_or_none()
    binding = session.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.tenant_id == tenant_id,
            TenantWorkspaceBinding.installation_id == payload.installation_id,
            TenantWorkspaceBinding.workspace_id == payload.workspace_id,
            TenantWorkspaceBinding.status == "ACTIVE",
        )
    ).one_or_none()
    catalog = session.get(AgentCatalogDefinition, payload.catalog_definition_id)
    if installation is None or binding is None:
        raise HTTPException(
            status_code=409, detail="Active owned SignalLoop binding is required"
        )
    if installation.local_identifier != payload.workspace_id:
        raise HTTPException(
            status_code=409, detail="Workspace does not match installation"
        )
    if (
        catalog is None
        or catalog.lifecycle_status != "PUBLISHED"
        or AgentType(catalog.agent_type) is not payload.agent_type
    ):
        raise HTTPException(
            status_code=409, detail="Published matching agent catalog is required"
        )
    if session.exec(
        select(AgentDeployment).where(
            AgentDeployment.tenant_id == tenant_id,
            AgentDeployment.name == payload.name,
        )
    ).one_or_none():
        raise HTTPException(
            status_code=409, detail="Agent deployment name already exists"
        )

    deployment = AgentDeployment(
        tenant_id=tenant_id,
        installation_id=payload.installation_id,
        workspace_id=payload.workspace_id,
        catalog_definition_id=payload.catalog_definition_id,
        agent_type=payload.agent_type,
        name=payload.name,
        purpose=payload.purpose,
        owner_user_id=payload.owner_user_id,
        configuration=payload.configuration,
        configuration_digest=_configuration_digest(payload.configuration),
        policy_profile=payload.policy_profile,
        locale=payload.locale,
        timezone=payload.timezone,
        environment=payload.environment,
    )
    session.add(deployment)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="agent.deployment.created",
        workspace_id=payload.workspace_id,
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="agent_deployment",
        resource_id=str(deployment.id),
        payload={
            "agent_type": payload.agent_type.value,
            "catalog_definition_id": str(payload.catalog_definition_id),
            "tenant_id": str(tenant_id),
        },
    )
    return _deployment_public(deployment)


async def _run_lifecycle_mutation(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    idempotency_key: str,
    action: str,
    mutation: Callable[[], AgentDeployment],
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _authorize_agent_admin(session, user, tenant_id)

    def mutate_once() -> dict[str, Any]:
        try:
            deployment = mutation()
        except AgentRegistryError as exc:
            if "not found" in str(exc):
                raise HTTPException(
                    status_code=404, detail="Agent deployment not found"
                ) from exc
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        append_audit_event_to_session(
            session,
            event_name=f"agent.deployment.{action}",
            workspace_id=deployment.workspace_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="agent_deployment",
            resource_id=str(deployment.id),
            payload={
                "agent_type": AgentType(deployment.agent_type).value,
                "lifecycle_version": deployment.lifecycle_version,
                "tenant_id": str(tenant_id),
            },
        )
        return _deployment_public(deployment)

    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=str(tenant_id),
        operation=f"commercial-agent:{deployment_id}:{action}",
        request_payload=request_payload or {},
        mutation=mutate_once,
        safe_to_retry_on_failure=True,
    )


@router.post("/tenants/{tenant_id}/deployments/{deployment_id}/validate")
async def validate_agent_deployment(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _run_lifecycle_mutation(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        idempotency_key=idempotency_key,
        action="validated",
        mutation=lambda: validate_deployment(
            session, tenant_id=tenant_id, deployment_id=deployment_id
        ),
    )


@router.post("/tenants/{tenant_id}/deployments/{deployment_id}/activate")
async def activate_agent_deployment(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _run_lifecycle_mutation(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        idempotency_key=idempotency_key,
        action="activated",
        mutation=lambda: activate_deployment(
            session,
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
        ),
    )


@router.post("/tenants/{tenant_id}/deployments/{deployment_id}/suspend")
async def suspend_agent_deployment(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    payload: AgentLifecycleReason,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _run_lifecycle_mutation(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        idempotency_key=idempotency_key,
        action="suspended",
        request_payload=payload.model_dump(),
        mutation=lambda: suspend_deployment(
            session,
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            reason=payload.reason,
        ),
    )


@router.post("/tenants/{tenant_id}/deployments/{deployment_id}/resume")
async def resume_agent_deployment(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _run_lifecycle_mutation(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        idempotency_key=idempotency_key,
        action="resumed",
        mutation=lambda: resume_deployment(
            session,
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
        ),
    )


@router.post("/tenants/{tenant_id}/deployments/{deployment_id}/retire")
async def retire_agent_deployment(
    request: Request,
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    deployment_id: uuid.UUID,
    payload: AgentLifecycleReason,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, Any]:
    return await _run_lifecycle_mutation(
        request,
        session=session,
        user=user,
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        idempotency_key=idempotency_key,
        action="retired",
        request_payload=payload.model_dump(),
        mutation=lambda: retire_deployment(
            session,
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            reason=payload.reason,
        ),
    )
