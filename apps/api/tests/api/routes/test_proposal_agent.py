from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
    AgentUsageLedger,
    AgentUsageState,
)
from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.proposal_agent.generation import claim_digest
from app.domain.proposal_agent.models import ProposalJobStatus
from app.domain.proposal_agent.service import enqueue_proposal_job
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
from app.domain.workspaces.models import Workspace
from app.models import User


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
            "ecrm_cell_id": binding.ecrm_cell_id,
            "client_account_id": "ara-global",
            "reference": "client:ara-global:approved:v1",
            "source_version": "v1",
            "source_digest": "a" * 64,
            "evidence_receipt_id": "ecrm-source-receipt-1",
            "allowed_claim_types": ["CLIENT_FACT"],
            "allowed_claim_digests": [claim_digest("CLIENT_FACT", claim_text)],
        },
    )

    blocked = client.post(url, headers=headers, json=payload)
    source_id = source_response.json()["id"]
    approval_url = f"{source_url}/{source_id}/approve"
    approval_payload = {
        "workspace_id": deployment.workspace_id,
        "ecrm_cell_id": binding.ecrm_cell_id,
        "client_account_id": "ara-global",
        "source_version": "v1",
        "source_digest": "a" * 64,
        "evidence_receipt_id": "ecrm-source-receipt-1",
    }
    self_approval = client.post(
        approval_url,
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"proposal-source-approval-{uuid.uuid4()}",
        },
        json=approval_payload,
    )
    approver_headers = _second_superuser_headers(db)
    approved = client.post(
        approval_url,
        headers={
            **approver_headers,
            "Idempotency-Key": f"proposal-source-approval-{uuid.uuid4()}",
        },
        json=approval_payload,
    )
    created = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)

    assert source_response.status_code == 201
    assert source_response.json()["status"] == "DRAFT"
    assert blocked.status_code == 409
    assert self_approval.status_code == 409
    assert approved.status_code == 200
    assert approved.json()["status"] == "PUBLISHED"
    assert created.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == created.json()
    assert created.json()["review_state"] == "DRAFT_REVIEW_REQUIRED"


def _second_superuser_headers(db: Session) -> dict[str, str]:
    user = User(
        email=f"proposal-approver-{uuid.uuid4().hex[:8]}@example.test",
        hashed_password="unused",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    return {
        "Authorization": (
            "Bearer "
            + create_access_token(subject=user.id, expires_delta=timedelta(minutes=10))
        )
    }


def test_admin_negatively_reconciles_unknown_job_with_durable_replay(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    from app.api.routes import proposal_agent as route_module

    tenant, deployment, binding = _proposal_agent(db)
    job = enqueue_proposal_job(
        db,
        tenant_id=tenant.id,
        workspace_id=deployment.workspace_id,
        deployment_id=deployment.id,
        ecrm_cell_id=binding.ecrm_cell_id,
        client_account_id="ara-global",
        proposal_id=f"proposal-{uuid.uuid4().hex[:8]}",
        mode="TEMPLATE",
        command_key=f"proposal-command-{uuid.uuid4()}",
        input_digest="b" * 64,
        source_digest="c" * 64,
        request_payload={"templateVersionId": "template-v1"},
    )
    usage = AgentUsageLedger(
        tenant_id=tenant.id,
        workspace_id=deployment.workspace_id,
        deployment_id=deployment.id,
        billing_day=date.today(),
        capacity_metric="proposal_version",
        idempotency_key=f"proposal-generation:{job.id}:1",
        state=AgentUsageState.UNKNOWN,
        reserved_units=1,
    )
    db.add(usage)
    db.flush()
    job.status = ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
    job.usage_reservation_id = usage.id
    db.add(job)
    db.commit()

    class ConfirmedAbsentAdapter:
        def lookup_receipt(self, command_key: str):  # noqa: ARG002
            return None

    monkeypatch.setattr(route_module, "_load_adapter", ConfirmedAbsentAdapter)
    url = (
        f"{settings.API_V1_STR}/proposal-agent/tenants/{tenant.id}/jobs/{job.id}/reconcile"
    )
    headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"proposal-reconcile-{uuid.uuid4()}",
    }
    payload = {
        "workspace_id": deployment.workspace_id,
        "accepted": False,
        "evidence_receipt_id": "ecrm-absence-check-1",
        "reason": "eCRM confirmed no version exists",
    }

    reconciled = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)

    assert reconciled.status_code == 200
    assert replay.json() == reconciled.json()
    assert reconciled.json()["status"] == "RETRY_SCHEDULED"


def test_admin_replays_dead_letter_with_durable_replay(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, deployment, binding = _proposal_agent(db)
    job = enqueue_proposal_job(
        db,
        tenant_id=tenant.id,
        workspace_id=deployment.workspace_id,
        deployment_id=deployment.id,
        ecrm_cell_id=binding.ecrm_cell_id,
        client_account_id="ara-global",
        proposal_id=f"proposal-{uuid.uuid4().hex[:8]}",
        mode="TEMPLATE",
        command_key=f"proposal-command-{uuid.uuid4()}",
        input_digest="d" * 64,
        source_digest="e" * 64,
        request_payload={"templateVersionId": "template-v1"},
    )
    job.status = ProposalJobStatus.DEAD_LETTER
    db.add(job)
    db.commit()
    url = (
        f"{settings.API_V1_STR}/proposal-agent/tenants/{tenant.id}/jobs/{job.id}/replay"
    )
    headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"proposal-replay-{uuid.uuid4()}",
    }
    payload = {
        "workspace_id": deployment.workspace_id,
        "reason": "operator confirmed transient eCRM outage",
    }

    replayed = client.post(url, headers=headers, json=payload)
    replay = client.post(url, headers=headers, json=payload)

    assert replayed.status_code == 200
    assert replay.json() == replayed.json()
    assert replayed.json()["status"] == "PENDING"


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
