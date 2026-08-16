from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)
from app.domain.workspaces.models import Workspace
from tests.utils.user import authentication_token_from_email


def _tenant_registry(
    db: Session,
) -> tuple[Tenant, ProductInstallation, Workspace, AgentCatalogDefinition]:
    suffix = uuid.uuid4().hex[:10]
    tenant = Tenant(key=f"agents-{suffix}", display_name="Agent API Tenant")
    workspace = Workspace(id=f"agents-{suffix}", name="Agent API Workspace")
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
        catalog_version=3_000_000 + int(suffix[:5], 16),
        display_name="Lead Preparation Agent",
        sellable_outcome="Prepare leads",
        default_capacity_metric="prepared_lead",
        default_capacity_amount=500,
        configuration_schema_version="lead-preparation.v1",
    )
    entitlement = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="launch-5",
        contract_version="2026-08",
        purchased_slots=5,
    )
    db.add_all([catalog, entitlement])
    db.commit()
    return tenant, installation, workspace, catalog


def _create_payload(
    installation: ProductInstallation,
    workspace: Workspace,
    catalog: AgentCatalogDefinition,
) -> dict[str, object]:
    return {
        "installation_id": str(installation.id),
        "workspace_id": workspace.id,
        "catalog_definition_id": str(catalog.id),
        "agent_type": AgentType.LEAD_PREPARATION.value,
        "name": "Primary lead preparation",
        "purpose": "Prepare qualified leads",
        "configuration": {"score_policy": "default-v1"},
        "policy_profile": "outbound-standard",
        "locale": "en-IN",
        "timezone": "Asia/Kolkata",
    }


def test_admin_creates_and_activates_agent_with_durable_replay(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, installation, workspace, catalog = _tenant_registry(db)
    create_url = (
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments"
    )
    create_headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"create-{uuid.uuid4()}",
    }

    created = client.post(
        create_url,
        headers=create_headers,
        json=_create_payload(installation, workspace, catalog),
    )
    replay = client.post(
        create_url,
        headers=create_headers,
        json=_create_payload(installation, workspace, catalog),
    )

    assert created.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == created.json()
    catalog_response = client.get(
        f"{settings.API_V1_STR}/commercial-agents/catalog",
        headers=superuser_token_headers,
    )
    entitlement_response = client.get(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/entitlement",
        headers=superuser_token_headers,
    )
    deployments_response = client.get(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments",
        headers=superuser_token_headers,
    )
    assert catalog_response.status_code == 200
    assert any(item["id"] == str(catalog.id) for item in catalog_response.json())
    assert entitlement_response.json()["purchased_slots"] == 5
    assert [item["id"] for item in deployments_response.json()] == [
        created.json()["id"]
    ]
    deployment_id = created.json()["id"]
    validated = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments/{deployment_id}/validate",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"validate-{uuid.uuid4()}",
        },
    )
    assert validated.status_code == 200
    assert validated.json()["status"] == AgentDeploymentStatus.DRAFT.value
    activate_headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"activate-{uuid.uuid4()}",
    }
    activated = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments/{deployment_id}/activate",
        headers=activate_headers,
    )
    activation_replay = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments/{deployment_id}/activate",
        headers=activate_headers,
    )

    assert activated.status_code == 200
    assert activation_replay.json() == activated.json()
    assert activated.json()["status"] == AgentDeploymentStatus.ACTIVE.value
    suspended = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments/{deployment_id}/suspend",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"suspend-{uuid.uuid4()}",
        },
        json={"reason": "planned maintenance"},
    )
    resumed = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments/{deployment_id}/resume",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"resume-{uuid.uuid4()}",
        },
    )
    retired = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments/{deployment_id}/retire",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"retire-{uuid.uuid4()}",
        },
        json={"reason": "contract ended"},
    )
    assert suspended.json()["status"] == AgentDeploymentStatus.SUSPENDED.value
    assert resumed.json()["status"] == AgentDeploymentStatus.ACTIVE.value
    assert retired.json()["status"] == AgentDeploymentStatus.RETIRED.value
    audit_names = db.exec(
        select(AuditEvent.event_name).where(AuditEvent.resource_id == deployment_id)
    ).all()
    assert "agent.deployment.created" in audit_names
    assert "agent.deployment.activated" in audit_names


def test_create_requires_idempotency_key_and_rejects_secret_configuration(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, installation, workspace, catalog = _tenant_registry(db)
    url = f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments"
    payload = _create_payload(installation, workspace, catalog)

    missing = client.post(url, headers=superuser_token_headers, json=payload)
    payload["configuration"] = {"api_key": "must-not-be-stored"}
    secret = client.post(
        url,
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"secret-{uuid.uuid4()}",
        },
        json=payload,
    )

    assert missing.status_code == 400
    assert secret.status_code == 422


def test_changed_payload_with_same_key_conflicts_and_cross_tenant_id_is_hidden(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, installation, workspace, catalog = _tenant_registry(db)
    other = Tenant(key=f"other-{uuid.uuid4().hex[:10]}", display_name="Other Tenant")
    db.add(other)
    db.commit()
    url = f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments"
    key = f"conflict-{uuid.uuid4()}"
    payload = _create_payload(installation, workspace, catalog)
    created = client.post(
        url,
        headers={**superuser_token_headers, "Idempotency-Key": key},
        json=payload,
    )
    changed_payload = {**payload, "name": "Changed name"}
    conflict = client.post(
        url,
        headers={**superuser_token_headers, "Idempotency-Key": key},
        json=changed_payload,
    )
    hidden = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{other.id}/deployments/{created.json()['id']}/activate",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"cross-{uuid.uuid4()}",
        },
    )

    assert created.status_code == 201
    assert conflict.status_code == 409
    assert hidden.status_code == 404


def test_user_without_tenant_agent_capability_is_denied(
    client: TestClient,
    db: Session,
) -> None:
    tenant, installation, workspace, catalog = _tenant_registry(db)
    headers = authentication_token_from_email(
        client=client,
        email=f"agent-denied-{uuid.uuid4().hex}@example.com",
        db=db,
    )
    response = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments",
        headers={**headers, "Idempotency-Key": f"denied-{uuid.uuid4()}"},
        json=_create_payload(installation, workspace, catalog),
    )
    assert response.status_code == 403


def test_platform_admin_provisions_agent_plan_idempotently(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    suffix = uuid.uuid4().hex[:10]
    tenant = Tenant(key=f"plan-{suffix}", display_name="Plan Tenant")
    workspace = Workspace(id=f"plan-{suffix}", name="Plan Workspace")
    db.add_all([tenant, workspace])
    db.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    db.add(installation)
    db.commit()
    url = f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/entitlement"
    headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"plan-{uuid.uuid4()}",
    }
    payload = {
        "installation_id": str(installation.id),
        "plan_code": "launch-5",
        "contract_version": "pilot-2026-08",
        "purchased_slots": 5,
        "allowed_agent_types": [
            AgentType.LEAD_PREPARATION.value,
            AgentType.EMAIL_OUTREACH.value,
        ],
        "type_ceilings": {AgentType.EMAIL_OUTREACH.value: 3},
        "billing_timezone": "Asia/Kolkata",
        "billing_day_start_hour": 0,
        "contract_reference": "ARA-PILOT-001",
    }

    created = client.put(url, headers=headers, json=payload)
    replay = client.put(url, headers=headers, json=payload)

    assert created.status_code == 200
    assert replay.json() == created.json()
    assert created.json()["purchased_slots"] == 5
    assert created.json()["type_ceilings"] == {AgentType.EMAIL_OUTREACH.value: 3}
