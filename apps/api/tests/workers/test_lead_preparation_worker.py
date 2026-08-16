from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine, func, select

from app.domain.audit.audit_events import AuditEvent
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
from app.domain.lead_preparation.models import (
    LeadEvidenceItem,
    LeadPreparationJob,
    LeadPreparationJobStatus,
    LeadPreparationPackage,
    LeadScoreVersion,
    LeadScoringPolicy,
)
from app.domain.lead_preparation.scoring import build_default_scoring_policy
from app.domain.lead_preparation.service import (
    claim_preparation_job,
    enqueue_preparation_job,
    recover_expired_preparation_leases,
)
from app.domain.lead_preparation.worker import run_lead_preparation_batch
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
from app.domain.workspaces.models import Workspace
from app.domain_models import Contact


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            ProductInstallation.__table__,
            Workspace.__table__,
            Contact.__table__,
            AgentCatalogDefinition.__table__,
            AgentPlanEntitlement.__table__,
            AgentDeployment.__table__,
            AgentCapacityOverride.__table__,
            AgentUsageLedger.__table__,
            AgentLifecycleEvent.__table__,
            AuditEvent.__table__,
            LeadScoringPolicy.__table__,
            LeadEvidenceItem.__table__,
            LeadScoreVersion.__table__,
            LeadPreparationPackage.__table__,
            LeadPreparationJob.__table__,
        ],
    )
    return Session(engine)


def _context(
    session: Session, *, suppressed: bool = False, max_attempts: int = 3
) -> tuple[AgentDeployment, Contact, LeadScoringPolicy, LeadPreparationJob]:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(key=f"lead-{suffix}", display_name="Lead Tenant")
    workspace = Workspace(id=f"lead-{suffix}", name="Lead Workspace")
    session.add_all([tenant, workspace])
    session.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    contact = Contact(
        workspace_id=workspace.id,
        email=f"lead-{suffix}@example.com",
        first_name="Ada",
        company="Analytical",
        phone="+15551234567",
        source_channel="web",
        tags_json=["chatbot-lead"],
        intent_json=["pricing"],
        consent_email=True,
        consent_voice=True,
        suppressed=suppressed,
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add_all([installation, contact])
    session.flush()
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.LEAD_PREPARATION,
        catalog_version=1,
        display_name="Lead Preparation Agent",
        sellable_outcome="Prepare leads",
        default_capacity_metric="prepared_lead",
        default_capacity_amount=10,
        configuration_schema_version="lead-preparation.v1",
    )
    entitlement = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="lead-test",
        contract_version="2026-08",
        purchased_slots=1,
        billing_timezone="UTC",
    )
    session.add_all([catalog, entitlement])
    session.flush()
    deployment = AgentDeployment(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.LEAD_PREPARATION,
        name=f"Lead agent {suffix}",
        status=AgentDeploymentStatus.ACTIVE,
        configuration={},
        configuration_digest="a" * 64,
    )
    policy = build_default_scoring_policy(
        tenant_id=tenant.id, workspace_id=workspace.id, version=1
    )
    session.add_all([deployment, policy])
    session.commit()
    job = enqueue_preparation_job(
        session,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        deployment_id=deployment.id,
        contact_id=contact.id,
        policy_id=policy.id,
        event_key=f"contact:{contact.id}:changed",
        max_attempts=max_attempts,
    )
    session.commit()
    return deployment, contact, policy, job


def test_event_enqueue_and_claim_are_idempotent_and_atomic() -> None:
    with _session() as session:
        deployment, contact, policy, job = _context(session)
        replay = enqueue_preparation_job(
            session,
            tenant_id=deployment.tenant_id,
            workspace_id=deployment.workspace_id,
            deployment_id=deployment.id,
            contact_id=contact.id,
            policy_id=policy.id,
            event_key=job.event_key,
        )
        assert replay.id == job.id

        first = claim_preparation_job(session, now=datetime.now(timezone.utc))
        second = claim_preparation_job(session, now=datetime.now(timezone.utc))
        assert first is not None
        assert second is None
        assert session.exec(select(func.count(LeadPreparationJob.id))).one() == 1


def test_success_creates_immutable_package_and_finalized_capacity() -> None:
    with _session() as session:
        _, _, _, job = _context(session)

        processed = run_lead_preparation_batch(
            session,
            evidence_collector=lambda _: {
                "source_type": "contact_profile",
                "source_reference": "internal:contact",
                "redacted_excerpt": "Known company and buyer intent",
            },
        )

        session.refresh(job)
        assert processed == 1
        assert job.status == LeadPreparationJobStatus.COMPLETED
        assert session.exec(select(func.count(LeadScoreVersion.id))).one() == 1
        assert session.exec(select(func.count(LeadPreparationPackage.id))).one() == 1
        usage = session.exec(select(AgentUsageLedger)).one()
        assert usage.state == AgentUsageState.FINALIZED
        assert session.exec(select(func.count(AuditEvent.id))).one() == 1


def test_suppressed_contact_finishes_without_capacity_or_drafts() -> None:
    with _session() as session:
        _, _, _, job = _context(session, suppressed=True)

        run_lead_preparation_batch(session, evidence_collector=lambda _: {})

        session.refresh(job)
        assert job.status == LeadPreparationJobStatus.SUPPRESSED
        assert session.exec(select(func.count(AgentUsageLedger.id))).one() == 0
        assert session.exec(select(func.count(LeadPreparationPackage.id))).one() == 0


def test_evidence_failures_back_off_then_dead_letter() -> None:
    with _session() as session:
        _, _, _, job = _context(session, max_attempts=2)
        now = datetime.now(timezone.utc)

        def fail(_: Contact) -> dict[str, str]:
            raise RuntimeError("source unavailable")

        run_lead_preparation_batch(session, evidence_collector=fail, now=now)
        session.refresh(job)
        assert job.status == LeadPreparationJobStatus.RETRY_SCHEDULED
        assert _utc(job.available_at) > now

        job.available_at = now
        session.add(job)
        session.commit()
        run_lead_preparation_batch(session, evidence_collector=fail, now=now)
        session.refresh(job)
        assert job.status == LeadPreparationJobStatus.DEAD_LETTER


def test_stale_lease_is_recovered_for_safe_internal_work() -> None:
    with _session() as session:
        _, _, _, job = _context(session)
        now = datetime.now(timezone.utc)
        claimed = claim_preparation_job(session, now=now)
        assert claimed is not None
        claimed.lease_expires_at = now - timedelta(seconds=1)
        session.add(claimed)
        session.commit()

        repaired = recover_expired_preparation_leases(session, now=now)
        session.commit()
        session.refresh(job)

        assert repaired == 1
        assert job.status == LeadPreparationJobStatus.RETRY_SCHEDULED
