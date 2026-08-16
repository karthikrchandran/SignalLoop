from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, func, select

from app.core.encryption import decrypt
from app.domain.audit.audit_events import AuditEvent
from app.domain.commercial_agents.models import (
    AgentCapacityOverride,
    AgentCatalogDefinition,
    AgentDependency,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentLifecycleEvent,
    AgentPlanEntitlement,
    AgentType,
    AgentUsageLedger,
    AgentUsageState,
)
from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.proposal_agent.ecrm_adapter import (
    EcrmProposalCommand,
    EcrmProposalReceipt,
)
from app.domain.proposal_agent.models import (
    ProposalDraftReview,
    ProposalEmailHandoff,
    ProposalGenerationEvidence,
    ProposalGenerationJob,
    ProposalGenerationReceipt,
    ProposalJobStatus,
)
from app.domain.proposal_agent.service import (
    ProposalAgentError,
    enqueue_proposal_job,
    reconcile_unknown_proposal_job,
    recover_expired_proposal_leases,
    replay_dead_letter_proposal_job,
    run_proposal_batch,
)
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
from app.domain.workspaces.models import Workspace


class AcceptingAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self.receipts: dict[str, EcrmProposalReceipt] = {}

    def apply(self, command: EcrmProposalCommand) -> EcrmProposalReceipt:
        self.calls += 1
        receipt = EcrmProposalReceipt(
            command_key=command.command_key,
            proposal_id=command.proposal_id,
            version_id=f"version-{command.command_key}",
            version_number=2,
            content_digest=command.payload_digest,
            artifact_digest="f" * 64,
            receipt_id=f"receipt-{command.command_key}",
        )
        self.receipts[command.command_key] = receipt
        return receipt

    def lookup_receipt(self, command_key: str) -> EcrmProposalReceipt | None:
        return self.receipts.get(command_key)


class LostResponseAdapter(AcceptingAdapter):
    def apply(self, command: EcrmProposalCommand) -> EcrmProposalReceipt:
        receipt = super().apply(command)
        assert receipt
        raise TimeoutError("eCRM accepted command but response was lost")


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
            AgentCapacityOverride.__table__,
            AgentUsageLedger.__table__,
            AgentLifecycleEvent.__table__,
            EcrmInstallationBinding.__table__,
            AuditEvent.__table__,
            ProposalGenerationJob.__table__,
            ProposalGenerationEvidence.__table__,
            ProposalGenerationReceipt.__table__,
            ProposalEmailHandoff.__table__,
            ProposalDraftReview.__table__,
        ],
    )
    return Session(engine)


def _context(
    session: Session, *, max_attempts: int = 3
) -> tuple[AgentDeployment, ProposalGenerationJob]:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(key=f"proposal-{suffix}", display_name="Proposal Tenant")
    workspace = Workspace(id=f"proposal-{suffix}", name="Proposal Workspace")
    session.add_all([tenant, workspace])
    session.flush()
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
    session.add_all([installation, binding])
    session.flush()
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.PROPOSAL_DRAFTING,
        catalog_version=5_000_000 + int(suffix[:5], 16),
        display_name="Proposal Agent",
        sellable_outcome="Create proposal versions",
        default_capacity_metric="proposal_version",
        default_capacity_amount=10,
        configuration_schema_version="proposal-drafting.v1",
    )
    plan = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="proposal-test",
        contract_version=f"test-{suffix}",
        purchased_slots=1,
        billing_timezone="UTC",
    )
    session.add_all([catalog, plan])
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
        configuration_digest="a" * 64,
    )
    session.add(deployment)
    session.commit()
    job = enqueue_proposal_job(
        session,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        deployment_id=deployment.id,
        ecrm_cell_id=binding.ecrm_cell_id,
        client_account_id=f"client-{suffix}",
        proposal_id=f"proposal-{suffix}",
        mode="TEMPLATE",
        command_key=f"proposal:{suffix}:v2",
        input_digest="b" * 64,
        source_digest="c" * 64,
        request_payload={
            "clientName": "ARA Global",
            "templateVersionId": "template-v1",
        },
        max_attempts=max_attempts,
    )
    session.commit()
    return deployment, job


def test_job_is_cell_bound_idempotent_and_payload_is_encrypted() -> None:
    with _session() as session:
        deployment, job = _context(session)
        replay = enqueue_proposal_job(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            deployment_id=deployment.id,
            ecrm_cell_id=job.ecrm_cell_id,
            client_account_id=job.client_account_id,
            proposal_id=job.proposal_id,
            mode=job.mode,
            command_key=job.command_key,
            input_digest=job.input_digest,
            source_digest=job.source_digest,
            request_payload={
                "clientName": "ARA Global",
                "templateVersionId": "template-v1",
            },
        )
        assert replay.id == job.id
        assert "ARA Global" not in job.encrypted_request
        assert "ARA Global" in decrypt(job.encrypted_request)

        with pytest.raises(ProposalAgentError):
            enqueue_proposal_job(
                session,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                deployment_id=deployment.id,
                ecrm_cell_id="other-cell",
                client_account_id=job.client_account_id,
                proposal_id=job.proposal_id,
                mode=job.mode,
                command_key="other-command",
                input_digest=job.input_digest,
                source_digest=job.source_digest,
                request_payload={},
            )


def test_accepted_command_finalizes_receipt_capacity_and_audit() -> None:
    with _session() as session:
        _, job = _context(session)
        adapter = AcceptingAdapter()

        assert run_proposal_batch(session, adapter=adapter) == 1
        session.refresh(job)

        assert job.status == ProposalJobStatus.COMPLETED
        assert adapter.calls == 1
        assert session.exec(select(func.count(ProposalGenerationReceipt.id))).one() == 1
        usage = session.exec(select(AgentUsageLedger)).one()
        assert usage.state == AgentUsageState.FINALIZED
        assert session.exec(select(func.count(AuditEvent.id))).one() == 1


def test_lost_ecrm_response_is_not_retried_until_receipt_reconciliation() -> None:
    with _session() as session:
        _, job = _context(session)
        adapter = LostResponseAdapter()

        run_proposal_batch(session, adapter=adapter)
        run_proposal_batch(session, adapter=adapter)
        session.refresh(job)

        assert job.status == ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
        assert adapter.calls == 1
        reconciled = reconcile_unknown_proposal_job(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            adapter=adapter,
            actor_id=uuid.uuid4(),
            actor_role="tenant_owner",
            capabilities={"agents.admin.manage"},
        )
        session.commit()
        assert reconciled.status == ProposalJobStatus.COMPLETED


def test_expired_worker_cannot_finalize_an_accepted_proposal() -> None:
    with _session() as session:
        _, job = _context(session)

        class ExpiringAdapter(AcceptingAdapter):
            def apply(self, command: EcrmProposalCommand) -> EcrmProposalReceipt:
                receipt = super().apply(command)
                current = session.get(ProposalGenerationJob, job.id)
                assert current is not None
                current.lease_expires_at = datetime.now(timezone.utc) - timedelta(
                    seconds=1
                )
                session.add(current)
                session.commit()
                return receipt

        adapter = ExpiringAdapter()
        assert run_proposal_batch(session, adapter=adapter) == 1
        session.refresh(job)

        assert job.status == ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
        assert session.exec(select(func.count(ProposalGenerationReceipt.id))).one() == 0
        usage = session.exec(select(AgentUsageLedger)).one()
        assert usage.state == AgentUsageState.UNKNOWN


def test_expired_preinvoke_lease_retries_but_attempted_command_becomes_unknown() -> (
    None
):
    with _session() as session:
        _, safe_job = _context(session)
        _, attempted_job = _context(session)
        now = datetime.now(timezone.utc)
        for job in (safe_job, attempted_job):
            job.status = ProposalJobStatus.IN_PROGRESS
            job.lease_token = uuid.uuid4()
            job.lease_expires_at = now - timedelta(seconds=1)
        attempted_job.command_attempted_at = now - timedelta(minutes=1)
        session.add_all([safe_job, attempted_job])
        session.commit()

        assert recover_expired_proposal_leases(session, now=now) == 2
        session.commit()
        session.refresh(safe_job)
        session.refresh(attempted_job)
        assert safe_job.status == ProposalJobStatus.RETRY_SCHEDULED
        assert attempted_job.status == ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME


def test_dead_letter_replay_requires_agent_admin_and_is_audited() -> None:
    with _session() as session:
        _, job = _context(session)
        job.status = ProposalJobStatus.DEAD_LETTER
        session.add(job)
        session.commit()
        with pytest.raises(ProposalAgentError):
            replay_dead_letter_proposal_job(
                session,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                job_id=job.id,
                actor_id=uuid.uuid4(),
                actor_role="employee",
                capabilities=set(),
                reason="eCRM recovered",
            )
        replayed = replay_dead_letter_proposal_job(
            session,
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            actor_id=uuid.uuid4(),
            actor_role="tenant_owner",
            capabilities={"agents.admin.manage"},
            reason="eCRM recovered",
        )
        session.commit()
        assert replayed.status == ProposalJobStatus.PENDING
