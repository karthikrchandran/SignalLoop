from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, func, select

from app.domain.commercial_agents.capacity import (
    AgentCapacityExceeded,
    finalize_capacity,
    mark_capacity_unknown,
    reconcile_unknown_capacity,
    release_capacity,
    reserve_capacity,
)
from app.domain.commercial_agents.models import (
    AgentCapacityOverride,
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentLifecycleEvent,
    AgentPlanEntitlement,
    AgentType,
    AgentUsageLedger,
    AgentUsageState,
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
            AgentCapacityOverride.__table__,
            AgentUsageLedger.__table__,
            AgentLifecycleEvent.__table__,
        ],
    )
    return Session(engine)


def _active_deployment(session: Session, *, capacity: int = 2) -> AgentDeployment:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(key=f"capacity-{suffix}", display_name="Capacity Tenant")
    workspace = Workspace(id=f"capacity-{suffix}", name="Capacity Workspace")
    session.add_all([tenant, workspace])
    session.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    session.add(installation)
    session.flush()
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.PROPOSAL_DRAFTING,
        catalog_version=1,
        display_name="Proposal Agent",
        sellable_outcome="Create proposal versions",
        default_capacity_metric="proposal_version",
        default_capacity_amount=capacity,
        configuration_schema_version="proposal.v1",
    )
    entitlement = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="capacity-test",
        contract_version="2026-08",
        purchased_slots=1,
        billing_timezone="Asia/Kolkata",
    )
    session.add_all([catalog, entitlement])
    session.flush()
    deployment = AgentDeployment(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.PROPOSAL_DRAFTING,
        name=f"Proposal agent {suffix}",
        status=AgentDeploymentStatus.ACTIVE,
        configuration={},
        configuration_digest="f" * 64,
    )
    session.add(deployment)
    session.commit()
    return deployment


def test_same_usage_key_reserves_and_finalizes_once() -> None:
    with _session() as session:
        deployment = _active_deployment(session)
        reserved = reserve_capacity(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            capacity_metric="proposal_version",
            idempotency_key="proposal:123:v1",
        )
        replay = reserve_capacity(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            capacity_metric="proposal_version",
            idempotency_key="proposal:123:v1",
        )
        assert replay.id == reserved.id

        finalized = finalize_capacity(
            session,
            reservation_id=reserved.id,
            provider_receipt_id="ecrm-proposal-version-123-1",
            finalized_units=1,
            provider_units={"versions": 1},
        )
        session.commit()
        assert finalized.state == AgentUsageState.FINALIZED
        assert session.exec(select(func.count(AgentUsageLedger.id))).one() == 1


def test_pre_effect_failure_releases_capacity_for_safe_reuse() -> None:
    with _session() as session:
        deployment = _active_deployment(session, capacity=1)
        reservation = reserve_capacity(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            capacity_metric="proposal_version",
            idempotency_key="invalid-input",
        )
        released = release_capacity(
            session,
            reservation_id=reservation.id,
            reason="QUESTIONNAIRE_INVALID",
        )
        assert released.state == AgentUsageState.RELEASED
        second = reserve_capacity(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            capacity_metric="proposal_version",
            idempotency_key="valid-input",
        )
        assert second.state == AgentUsageState.RESERVED


def test_capacity_limit_counts_reserved_and_unknown_outcomes() -> None:
    with _session() as session:
        deployment = _active_deployment(session, capacity=1)
        reservation = reserve_capacity(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            capacity_metric="proposal_version",
            idempotency_key="ambiguous-provider-call",
        )
        mark_capacity_unknown(
            session,
            reservation_id=reservation.id,
            reason="PROVIDER_RESPONSE_LOST",
        )
        with pytest.raises(AgentCapacityExceeded):
            reserve_capacity(
                session,
                tenant_id=deployment.tenant_id,
                workspace_id=deployment.workspace_id,
                deployment_id=deployment.id,
                capacity_metric="proposal_version",
                idempotency_key="new-work",
            )


def test_unknown_outcome_requires_receipt_and_audits_reconciliation() -> None:
    with _session() as session:
        deployment = _active_deployment(session, capacity=1)
        reservation = reserve_capacity(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            capacity_metric="proposal_version",
            idempotency_key="provider-timeout",
        )
        mark_capacity_unknown(
            session,
            reservation_id=reservation.id,
            reason="PROVIDER_TIMEOUT",
        )
        reconciled = reconcile_unknown_capacity(
            session,
            reservation_id=reservation.id,
            accepted=False,
            provider_receipt_id="provider-not-found-456",
            actor_id=uuid.uuid4(),
            actor_role="TENANT_OWNER",
            reason="provider lookup proves no accepted work",
            now=datetime.now(timezone.utc),
        )
        session.commit()
        assert reconciled.state == AgentUsageState.RELEASED
        event = session.exec(
            select(AgentLifecycleEvent).where(
                AgentLifecycleEvent.event_type == "agent.capacity.reconciled"
            )
        ).one()
        assert event.payload["provider_receipt_id"] == "provider-not-found-456"
