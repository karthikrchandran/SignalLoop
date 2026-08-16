from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest
from sqlmodel import Session, func, select

from app.core.db import engine
from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.commercial_agents.service import (
    AgentSlotLimitExceeded,
    activate_deployment,
)
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)
from app.domain.workspaces.models import Workspace


def test_concurrent_activation_cannot_consume_the_final_slot(db: Session) -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("row-lock contention contract requires PostgreSQL")

    suffix = uuid.uuid4().hex[:10]
    tenant = Tenant(key=f"slot-race-{suffix}", display_name="Slot Race Tenant")
    workspace = Workspace(id=f"slot-race-{suffix}", name="Slot Race Workspace")
    db.add_all([tenant, workspace])
    db.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    db.add(installation)
    db.flush()
    db.add(
        TenantWorkspaceBinding(
            tenant_id=tenant.id,
            installation_id=installation.id,
            workspace_id=workspace.id,
        )
    )
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.LEAD_PREPARATION,
        catalog_version=1_000_000 + int(suffix[:5], 16),
        display_name="Race Lead Agent",
        sellable_outcome="Prove slot serialization",
        default_capacity_metric="prepared_lead",
        default_capacity_amount=500,
        configuration_schema_version="race.v1",
    )
    db.add(catalog)
    db.flush()
    db.add(
        AgentPlanEntitlement(
            tenant_id=tenant.id,
            installation_id=installation.id,
            plan_code="single-slot",
            contract_version="race-v1",
            purchased_slots=1,
        )
    )
    deployments = [
        AgentDeployment(
            tenant_id=tenant.id,
            installation_id=installation.id,
            workspace_id=workspace.id,
            catalog_definition_id=catalog.id,
            agent_type=AgentType.LEAD_PREPARATION,
            name=f"Race agent {index}-{suffix}",
            configuration={},
            configuration_digest=str(index) * 64,
        )
        for index in (1, 2)
    ]
    db.add_all(deployments)
    db.commit()
    tenant_id = tenant.id
    deployment_ids = [deployment.id for deployment in deployments]

    def activate(deployment_id: uuid.UUID) -> str:
        with Session(engine) as session:
            try:
                activate_deployment(
                    session,
                    tenant_id=tenant_id,
                    deployment_id=deployment_id,
                    actor_id=None,
                    actor_role="TEST",
                )
                session.commit()
                return "ACTIVE"
            except AgentSlotLimitExceeded:
                session.rollback()
                return "LIMITED"

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with Session(engine) as first_session:
            activate_deployment(
                first_session,
                tenant_id=tenant_id,
                deployment_id=deployment_ids[0],
                actor_id=None,
                actor_role="TEST",
            )
            second = pool.submit(activate, deployment_ids[1])
            with pytest.raises(FutureTimeoutError):
                second.result(timeout=0.5)
            first_session.commit()
            second_result = second.result(timeout=10)
    finally:
        pool.shutdown(wait=True)

    db.expire_all()
    active_count = db.exec(
        select(func.count(AgentDeployment.id)).where(
            AgentDeployment.tenant_id == tenant.id,
            AgentDeployment.status == AgentDeploymentStatus.ACTIVE,
        )
    ).one()
    assert second_result == "LIMITED"
    assert active_count == 1
