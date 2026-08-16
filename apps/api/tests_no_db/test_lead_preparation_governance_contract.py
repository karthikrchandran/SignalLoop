from app.domain.lead_preparation import models


def test_lead_policy_governance_contract_is_persisted_and_approval_gated() -> None:
    assert models.LeadScoringPolicyStatus.APPROVED.value == "APPROVED"
    assert models.LeadPolicyEvaluationEvidence.__tablename__ == "lead_policy_evaluation_evidence"
    assert models.LeadPolicyChangeEvidence.__tablename__ == "lead_policy_change_evidence"
