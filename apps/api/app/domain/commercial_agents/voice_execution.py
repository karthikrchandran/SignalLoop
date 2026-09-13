"""Resolve commercial voice-agent deployments for runtime execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    TenantWorkspaceBinding,
)


class VoiceDeploymentResolutionError(RuntimeError):
    """Raised when a workspace cannot safely run a voice deployment."""


@dataclass(frozen=True)
class ResolvedVoiceDeployment:
    deployment: AgentDeployment
    tenant_id: uuid.UUID
    workspace_id: str
    capacity_metric: str


def resolve_active_voice_deployment(
    session: Session,
    *,
    workspace_id: str,
) -> ResolvedVoiceDeployment:
    binding = session.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.workspace_id == workspace_id,
            TenantWorkspaceBinding.status == "ACTIVE",
        )
    ).one_or_none()
    if binding is None:
        raise VoiceDeploymentResolutionError("active tenant workspace binding is required")

    installation = session.get(ProductInstallation, binding.installation_id)
    if (
        installation is None
        or installation.tenant_id != binding.tenant_id
        or ProductCode(installation.product_code) is not ProductCode.SIGNAL_LOOP
        or installation.status != "ACTIVE"
    ):
        raise VoiceDeploymentResolutionError("active SignalLoop installation is required")

    deployment = session.exec(
        select(AgentDeployment).where(
            AgentDeployment.tenant_id == binding.tenant_id,
            AgentDeployment.installation_id == binding.installation_id,
            AgentDeployment.workspace_id == workspace_id,
            AgentDeployment.agent_type == AgentType.VOICE_CONVERSATION,
            AgentDeployment.status == AgentDeploymentStatus.ACTIVE,
        )
    ).one_or_none()
    if deployment is None:
        raise VoiceDeploymentResolutionError("active voice deployment is required")

    catalog = session.get(AgentCatalogDefinition, deployment.catalog_definition_id)
    if (
        catalog is None
        or AgentType(catalog.agent_type) is not AgentType.VOICE_CONVERSATION
        or catalog.lifecycle_status != "PUBLISHED"
    ):
        raise VoiceDeploymentResolutionError("published voice catalog definition is required")

    entitlement = session.exec(
        select(AgentPlanEntitlement).where(
            AgentPlanEntitlement.tenant_id == binding.tenant_id,
            AgentPlanEntitlement.installation_id == binding.installation_id,
            AgentPlanEntitlement.status == "ACTIVE",
        )
    ).first()
    if entitlement is None or AgentType.VOICE_CONVERSATION.value not in entitlement.allowed_agent_types:
        raise VoiceDeploymentResolutionError("active voice entitlement is required")

    return ResolvedVoiceDeployment(
        deployment=deployment,
        tenant_id=binding.tenant_id,
        workspace_id=workspace_id,
        capacity_metric=catalog.default_capacity_metric,
    )
