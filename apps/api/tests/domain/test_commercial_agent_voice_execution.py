from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.commercial_agents.voice_execution import (
    VoiceDeploymentResolutionError,
    resolve_active_voice_deployment,
)
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)
from app.domain.workspaces.models import Workspace


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            ProductInstallation.__table__,
            TenantWorkspaceBinding.__table__,
            Workspace.__table__,
            AgentCatalogDefinition.__table__,
            AgentPlanEntitlement.__table__,
            AgentDeployment.__table__,
        ],
    )
    return Session(engine)


def _voice_context(
    session: Session,
    *,
    workspace_id: str = "workspace_ara_global",
    deployment_status: AgentDeploymentStatus | None = AgentDeploymentStatus.ACTIVE,
) -> AgentDeployment | None:
    tenant = Tenant(key=f"tenant-{uuid.uuid4().hex[:8]}", display_name="ARA Global")
    workspace = Workspace(id=workspace_id, name="ARA Global")
    session.add_all([tenant, workspace])
    session.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    session.add(installation)
    session.flush()
    session.add(
        TenantWorkspaceBinding(
            tenant_id=tenant.id,
            installation_id=installation.id,
            workspace_id=workspace.id,
        )
    )
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.VOICE_CONVERSATION,
        catalog_version=1,
        display_name="Voice Conversation Agent",
        sellable_outcome="Governed outbound voice conversations",
        default_capacity_metric="voice_attempt",
        default_capacity_amount=100,
        configuration_schema_version="voice-conversation.v1",
        external_side_effects=True,
    )
    entitlement = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="voice-demo",
        contract_version="2026-09",
        purchased_slots=1,
        allowed_agent_types=[AgentType.VOICE_CONVERSATION.value],
    )
    session.add_all([catalog, entitlement])
    session.flush()
    if deployment_status is None:
        session.commit()
        return None
    deployment = AgentDeployment(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.VOICE_CONVERSATION,
        name="ARA voice agent",
        status=deployment_status,
        configuration={"provider": "twilio"},
        configuration_digest="a" * 64,
    )
    session.add(deployment)
    session.commit()
    session.refresh(deployment)
    return deployment


def test_resolves_exact_active_voice_deployment_for_workspace() -> None:
    with _session() as session:
        deployment = _voice_context(session)
        assert deployment is not None

        resolved = resolve_active_voice_deployment(
            session, workspace_id=deployment.workspace_id
        )

        assert resolved.deployment.id == deployment.id
        assert resolved.tenant_id == deployment.tenant_id
        assert resolved.workspace_id == deployment.workspace_id
        assert resolved.capacity_metric == "voice_attempt"


def test_rejects_workspace_without_active_voice_deployment() -> None:
    with _session() as session:
        _voice_context(session, deployment_status=AgentDeploymentStatus.SUSPENDED)

        with pytest.raises(VoiceDeploymentResolutionError, match="active voice"):
            resolve_active_voice_deployment(session, workspace_id="workspace_ara_global")


def test_rejects_workspace_without_active_tenant_binding() -> None:
    with _session() as session:
        session.add(Workspace(id="workspace_ara_global", name="ARA Global"))
        session.commit()

        with pytest.raises(VoiceDeploymentResolutionError, match="binding"):
            resolve_active_voice_deployment(session, workspace_id="workspace_ara_global")
