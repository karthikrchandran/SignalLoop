from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDependency,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentLifecycleEvent,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.commercial_agents.service import (
    AgentDependencyError,
    AgentOwnershipError,
    AgentSlotLimitExceeded,
    activate_deployment,
    resume_deployment,
    retire_deployment,
    suspend_deployment,
    validate_deployment,
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
            Workspace.__table__,
            AgentCatalogDefinition.__table__,
            AgentPlanEntitlement.__table__,
            AgentDeployment.__table__,
            AgentDependency.__table__,
            AgentLifecycleEvent.__table__,
            TenantWorkspaceBinding.__table__,
        ],
    )
    return Session(engine)


def _registry_context(
    session: Session,
) -> tuple[Tenant, ProductInstallation, Workspace]:
    tenant = Tenant(key="ara-global", display_name="ARA Global")
    workspace = Workspace(id="ara-sales", name="ARA Sales")
    session.add_all([tenant, workspace])
    session.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    session.add(installation)
    session.commit()
    return tenant, installation, workspace


def test_catalog_and_deployment_preserve_commercial_contract() -> None:
    with _session() as session:
        tenant, installation, workspace = _registry_context(session)
        catalog = AgentCatalogDefinition(
            agent_type=AgentType.LEAD_PREPARATION,
            catalog_version=1,
            display_name="Lead Preparation Agent",
            sellable_outcome="Prepare and score leads",
            default_capacity_metric="prepared_lead",
            default_capacity_amount=500,
            configuration_schema_version="lead-preparation.v1",
            approved_at=datetime.now(timezone.utc),
        )
        entitlement = AgentPlanEntitlement(
            tenant_id=tenant.id,
            installation_id=installation.id,
            plan_code="launch-5",
            contract_version="2026-08",
            purchased_slots=5,
            billing_timezone="Asia/Kolkata",
        )
        session.add_all([catalog, entitlement])
        session.flush()
        deployment = AgentDeployment(
            tenant_id=tenant.id,
            installation_id=installation.id,
            workspace_id=workspace.id,
            catalog_definition_id=catalog.id,
            agent_type=AgentType.LEAD_PREPARATION,
            name="ARA lead preparation",
            purpose="Prepare ARA sales leads",
            configuration={"score_policy": "default-v1"},
            configuration_digest="a" * 64,
        )
        session.add(deployment)
        session.commit()

        stored = session.exec(select(AgentDeployment)).one()
        assert stored.status == AgentDeploymentStatus.DRAFT
        assert stored.agent_type == AgentType.LEAD_PREPARATION
        assert stored.tenant_id == tenant.id
        assert stored.workspace_id == workspace.id
        assert entitlement.purchased_slots == 5
        assert catalog.default_capacity_amount == 500


def test_catalog_version_is_unique_per_agent_type() -> None:
    with _session() as session:
        session.add_all(
            [
                AgentCatalogDefinition(
                    agent_type=AgentType.EMAIL_OUTREACH,
                    catalog_version=1,
                    display_name="Email Agent",
                    sellable_outcome="Send governed email",
                    default_capacity_metric="accepted_send",
                    default_capacity_amount=1000,
                    configuration_schema_version="email.v1",
                ),
                AgentCatalogDefinition(
                    agent_type=AgentType.EMAIL_OUTREACH,
                    catalog_version=1,
                    display_name="Duplicate Email Agent",
                    sellable_outcome="Duplicate",
                    default_capacity_metric="accepted_send",
                    default_capacity_amount=1000,
                    configuration_schema_version="email.v1",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_deployment_name_is_unique_inside_tenant() -> None:
    with _session() as session:
        tenant, installation, workspace = _registry_context(session)
        catalog = AgentCatalogDefinition(
            agent_type=AgentType.CALENDAR_SCHEDULER,
            catalog_version=1,
            display_name="Calendar Scheduler",
            sellable_outcome="Book meetings",
            default_capacity_metric="scheduling_workflow",
            default_capacity_amount=100,
            configuration_schema_version="calendar.v1",
        )
        session.add(catalog)
        session.flush()
        common = {
            "tenant_id": tenant.id,
            "installation_id": installation.id,
            "workspace_id": workspace.id,
            "catalog_definition_id": catalog.id,
            "agent_type": AgentType.CALENDAR_SCHEDULER,
            "name": "Primary scheduler",
            "configuration": {},
            "configuration_digest": "b" * 64,
        }
        session.add(AgentDeployment(**common))
        session.commit()
        session.add(AgentDeployment(id=uuid.uuid4(), **common))
        with pytest.raises(IntegrityError):
            session.commit()


def _deployment(
    session: Session,
    *,
    agent_type: AgentType,
    name: str,
    slots: int = 5,
    configuration: dict[str, object] | None = None,
) -> AgentDeployment:
    tenant, installation, workspace = _registry_context(session)
    session.add(
        TenantWorkspaceBinding(
            tenant_id=tenant.id,
            installation_id=installation.id,
            workspace_id=workspace.id,
        )
    )
    catalog = AgentCatalogDefinition(
        agent_type=agent_type,
        catalog_version=1,
        display_name=name,
        sellable_outcome=name,
        default_capacity_metric="unit",
        default_capacity_amount=100,
        configuration_schema_version=f"{agent_type.value.lower()}.v1",
    )
    entitlement = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code=f"launch-{slots}",
        contract_version="2026-08",
        purchased_slots=slots,
    )
    session.add_all([catalog, entitlement])
    session.flush()
    deployment = AgentDeployment(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
        catalog_definition_id=catalog.id,
        agent_type=agent_type,
        name=name,
        configuration=configuration or {},
        configuration_digest="c" * 64,
    )
    session.add(deployment)
    session.commit()
    session.refresh(deployment)
    return deployment


def test_activation_writes_lifecycle_event_in_same_transaction() -> None:
    with _session() as session:
        deployment = _deployment(
            session, agent_type=AgentType.LEAD_PREPARATION, name="Lead prep"
        )

        activated = activate_deployment(
            session,
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            actor_id=uuid.uuid4(),
            actor_role="TENANT_OWNER",
        )
        session.commit()

        assert activated.status == AgentDeploymentStatus.ACTIVE
        event = session.exec(select(AgentLifecycleEvent)).one()
        assert event.event_type == "agent.deployment.activated"
        assert event.lifecycle_version == activated.lifecycle_version


def test_activation_rejects_deployment_beyond_purchased_slots() -> None:
    with _session() as session:
        first = _deployment(
            session,
            agent_type=AgentType.LEAD_PREPARATION,
            name="First agent",
            slots=1,
        )
        first.status = AgentDeploymentStatus.ACTIVE
        session.add(first)
        catalog = session.get(AgentCatalogDefinition, first.catalog_definition_id)
        assert catalog is not None
        second = AgentDeployment(
            tenant_id=first.tenant_id,
            installation_id=first.installation_id,
            workspace_id=first.workspace_id,
            catalog_definition_id=catalog.id,
            agent_type=AgentType.LEAD_PREPARATION,
            name="Second agent",
            configuration={},
            configuration_digest="d" * 64,
        )
        session.add(second)
        session.commit()

        with pytest.raises(AgentSlotLimitExceeded):
            activate_deployment(
                session,
                tenant_id=second.tenant_id,
                deployment_id=second.id,
                actor_id=uuid.uuid4(),
                actor_role="TENANT_OWNER",
            )


def test_campaign_manager_requires_explicit_active_channel_dependencies() -> None:
    with _session() as session:
        campaign_manager = _deployment(
            session,
            agent_type=AgentType.CAMPAIGN_MANAGER,
            name="Campaign manager",
            configuration={"channels": ["email", "voice"]},
        )

        with pytest.raises(AgentDependencyError):
            activate_deployment(
                session,
                tenant_id=campaign_manager.tenant_id,
                deployment_id=campaign_manager.id,
                actor_id=uuid.uuid4(),
                actor_role="TENANT_OWNER",
            )


def test_activation_rejects_cross_tenant_installation_ownership() -> None:
    with _session() as session:
        deployment = _deployment(
            session, agent_type=AgentType.CALENDAR_SCHEDULER, name="Scheduler"
        )
        other = Tenant(key="ai-consulting", display_name="AI Consulting")
        session.add(other)
        session.commit()
        deployment.tenant_id = other.id
        session.add(deployment)
        session.commit()

        with pytest.raises(AgentOwnershipError):
            activate_deployment(
                session,
                tenant_id=other.id,
                deployment_id=deployment.id,
                actor_id=uuid.uuid4(),
                actor_role="TENANT_OWNER",
            )


def test_suspension_preserves_slot_until_retirement_releases_it() -> None:
    with _session() as session:
        first = _deployment(
            session,
            agent_type=AgentType.LEAD_PREPARATION,
            name="Contracted lead agent",
            slots=1,
        )
        activate_deployment(
            session,
            tenant_id=first.tenant_id,
            deployment_id=first.id,
            actor_id=uuid.uuid4(),
            actor_role="TENANT_OWNER",
        )
        session.commit()
        suspended = suspend_deployment(
            session,
            tenant_id=first.tenant_id,
            deployment_id=first.id,
            actor_id=uuid.uuid4(),
            actor_role="TENANT_OWNER",
            reason="customer maintenance",
        )
        session.commit()
        assert suspended.status == AgentDeploymentStatus.SUSPENDED

        catalog = session.get(AgentCatalogDefinition, first.catalog_definition_id)
        assert catalog is not None
        second = AgentDeployment(
            tenant_id=first.tenant_id,
            installation_id=first.installation_id,
            workspace_id=first.workspace_id,
            catalog_definition_id=catalog.id,
            agent_type=AgentType.LEAD_PREPARATION,
            name="Replacement lead agent",
            configuration={},
            configuration_digest="e" * 64,
        )
        session.add(second)
        session.commit()
        with pytest.raises(AgentSlotLimitExceeded):
            activate_deployment(
                session,
                tenant_id=second.tenant_id,
                deployment_id=second.id,
                actor_id=uuid.uuid4(),
                actor_role="TENANT_OWNER",
            )

        retired = retire_deployment(
            session,
            tenant_id=first.tenant_id,
            deployment_id=first.id,
            actor_id=uuid.uuid4(),
            actor_role="TENANT_OWNER",
            reason="replacement activated",
        )
        session.commit()
        assert retired.status == AgentDeploymentStatus.RETIRED
        assert (
            activate_deployment(
                session,
                tenant_id=second.tenant_id,
                deployment_id=second.id,
                actor_id=uuid.uuid4(),
                actor_role="TENANT_OWNER",
            ).status
            == AgentDeploymentStatus.ACTIVE
        )


def test_resume_revalidates_deployment_contract() -> None:
    with _session() as session:
        deployment = _deployment(
            session, agent_type=AgentType.CALENDAR_SCHEDULER, name="Scheduler resume"
        )
        activate_deployment(
            session,
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            actor_id=None,
            actor_role="TENANT_OWNER",
        )
        suspend_deployment(
            session,
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            actor_id=None,
            actor_role="TENANT_OWNER",
            reason="maintenance",
        )
        session.commit()

        assert (
            validate_deployment(
                session,
                tenant_id=deployment.tenant_id,
                deployment_id=deployment.id,
            ).id
            == deployment.id
        )
        resumed = resume_deployment(
            session,
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            actor_id=None,
            actor_role="TENANT_OWNER",
        )
        session.commit()
        assert resumed.status == AgentDeploymentStatus.ACTIVE
