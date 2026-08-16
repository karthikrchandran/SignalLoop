from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.proposal_agent.generation import claim_digest
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
from app.domain.workspaces.models import Workspace


def test_admin_creates_grounded_generative_job_with_durable_replay(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, deployment, binding = _proposal_agent(db)
    claim_text = "ARA Global is the named client."
    payload = {
        "workspace_id": deployment.workspace_id,
        "deployment_id": str(deployment.id),
        "ecrm_cell_id": binding.ecrm_cell_id,
        "client_account_id": "ara-global",
        "proposal_id": f"proposal-{uuid.uuid4().hex[:8]}",
        "command_key": f"proposal-command-{uuid.uuid4()}",
        "draft": {
            "prompt_version": "proposal-grounded.v1",
            "model_id": "approved-model-2026-08",
            "claims": [
                {
                    "claim_type": "CLIENT_FACT",
                    "text": claim_text,
                    "source_references": ["client:ara-global:approved:v1"],
                }
            ],
        },
        "source_references": ["client:ara-global:approved:v1"],
    }
    headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"proposal-job-{uuid.uuid4()}",
    }
    url = f"{settings.API_V1_STR}/proposal-agent/tenants/{tenant.id}/generative-jobs"
    source_url = (
        f"{settings.API_V1_STR}/proposal-agent/tenants/{tenant.id}/grounding-sources"
    )
    source_response = client.post(
        source_url,
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"proposal-source-{uuid.uuid4()}",
        },
        json={
            "workspace_id": deployment.workspace_id,
            "reference": "client:ara-global:approved:v1",
            "source_digest": "a" * 64,
            "allowed_claim_types": ["CLIENT_FACT"],
            "allowed_claim_digests": [claim_digest("CLIENT_FACT", claim_text)],
        },
    )

    created = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)

    assert source_response.status_code == 201
    assert created.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == created.json()
    assert created.json()["review_state"] == "DRAFT_REVIEW_REQUIRED"


def _proposal_agent(
    db: Session,
) -> tuple[Tenant, AgentDeployment, EcrmInstallationBinding]:
    suffix = uuid.uuid4().hex[:10]
    tenant = Tenant(key=f"proposal-api-{suffix}", display_name="Proposal API")
    workspace = Workspace(id=f"proposal-{suffix}", name="Proposal API")
    db.add_all([tenant, workspace])
    db.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    binding = EcrmInstallationBinding(
        workspace_id=workspace.id,
        ecrm_cell_id=f"cell-{suffix}",
        ecrm_cell_key=f"cell-key-{suffix}",
        base_url="https://ecrm.example.test",
        credential_secret_ref=f"secret://ecrm/{suffix}",
        capabilities=["proposal.version.create", "proposal.receipt.lookup"],
    )
    db.add_all([installation, binding])
    db.flush()
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.PROPOSAL_DRAFTING,
        catalog_version=8_000_000 + int(suffix[:5], 16),
        display_name="Proposal Agent",
        sellable_outcome="Create governed proposals",
        default_capacity_metric="proposal_version",
        default_capacity_amount=10,
        configuration_schema_version="proposal.v1",
    )
    plan = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="proposal-test",
        contract_version=f"test-{suffix}",
        purchased_slots=1,
    )
    db.add_all([catalog, plan])
    db.flush()
    deployment = AgentDeployment(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.PROPOSAL_DRAFTING,
        name=f"Proposal Agent {suffix}",
        status=AgentDeploymentStatus.ACTIVE,
        configuration={},
        configuration_digest="f" * 64,
    )
    db.add(deployment)
    db.commit()
    return tenant, deployment, binding
