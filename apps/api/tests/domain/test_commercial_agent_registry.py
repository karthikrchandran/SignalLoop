from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
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
