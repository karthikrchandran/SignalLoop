import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.lead_preparation import models
from app.domain.lead_preparation import service as lead_service
from app.domain.lead_preparation.scoring import build_default_scoring_policy
from app.domain.tenants.models import Tenant


def test_lead_policy_governance_contract_is_persisted_and_approval_gated() -> None:
    assert models.LeadScoringPolicyStatus.APPROVED.value == "APPROVED"
    assert models.LeadPolicyEvaluationEvidence.__tablename__ == "lead_policy_evaluation_evidence"
    assert models.LeadPolicyChangeEvidence.__tablename__ == "lead_policy_change_evidence"


def test_policy_approval_requires_exact_persisted_evaluation_evidence() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            models.LeadScoringPolicy.__table__,
            models.LeadPolicyEvaluationEvidence.__table__,
        ],
    )
    with Session(engine) as session:
        tenant = Tenant(key=f"evidence-{uuid.uuid4().hex[:8]}", display_name="Evidence")
        session.add(tenant)
        session.flush()
        policy = build_default_scoring_policy(
            tenant_id=tenant.id, workspace_id="evidence-workspace", version=1
        )
        session.add(policy)
        session.flush()

        with pytest.raises(
            lead_service.LeadPreparationError, match="evaluation evidence"
        ):
            lead_service.require_policy_evaluation_evidence(session, policy=policy)

        lead_service.record_policy_evaluation_evidence(
            session,
            tenant_id=tenant.id,
            workspace_id=policy.workspace_id,
            contact_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            policy_digest="f" * 64,
            input_payload={"candidate": "mismatch"},
            result_payload={"score": 10},
        )
        with pytest.raises(
            lead_service.LeadPreparationError, match="evaluation evidence"
        ):
            lead_service.require_policy_evaluation_evidence(session, policy=policy)

        expected = lead_service.record_policy_evaluation_evidence(
            session,
            tenant_id=tenant.id,
            workspace_id=policy.workspace_id,
            contact_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            policy_digest=policy.policy_digest,
            input_payload={"candidate": "exact"},
            result_payload={"score": 85, "band": "HOT"},
        )

        assert (
            lead_service.require_policy_evaluation_evidence(session, policy=policy).id
            == expected.id
        )
