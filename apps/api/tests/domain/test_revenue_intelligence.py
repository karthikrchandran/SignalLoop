import pytest

from app.domain.revenue_intelligence.service import (
    EvidenceRequiredError,
    IdempotencyConflictError,
    RevenueIntelligenceService,
    TenantScopeError,
)


def test_signal_requires_tenant_and_auditable_evidence() -> None:
    service = RevenueIntelligenceService()

    signal = service.record_signal(
        tenant_key="ara-global",
        tenant_id="tenant-1",
        signal_type="stalled_opportunity",
        subject_ref="opportunity-7",
        confidence=0.91,
        evidence_refs=("event:crm-7",),
        evidence_hash="sha256:abc",
        source="revenue-os",
        idempotency_key="sig-1",
    )

    assert signal.tenant_key == "ara-global"
    assert signal.tenant_id == "tenant-1"
    assert signal.evidence_refs == ("event:crm-7",)
    assert signal.created_at.tzinfo is not None

    with pytest.raises(EvidenceRequiredError):
        service.record_signal(
            tenant_key="ara-global",
            tenant_id="tenant-1",
            signal_type="stalled_opportunity",
            subject_ref="opportunity-8",
            confidence=0.7,
            evidence_refs=(),
            evidence_hash="",
            source="revenue-os",
            idempotency_key="sig-2",
        )


def test_intervention_requires_consent_and_policy_decision() -> None:
    service = RevenueIntelligenceService()
    signal = service.record_signal(
        tenant_key="ai-consulting",
        tenant_id="tenant-2",
        signal_type="renewal_risk",
        subject_ref="account-4",
        confidence=0.8,
        evidence_refs=("ledger:4",),
        evidence_hash="sha256:def",
        source="revenue-os",
        idempotency_key="sig-2",
    )

    with pytest.raises(TenantScopeError):
        service.propose_intervention(
            tenant_key="ara-global",
            signal_id=signal.id,
            action="send_follow_up",
            consent_verified=True,
            policy_allowed=True,
            evidence_refs=("ledger:4",),
            idempotency_key="int-1",
        )

    with pytest.raises(ValueError, match="consent"):
        service.propose_intervention(
            tenant_key="ai-consulting",
            signal_id=signal.id,
            action="send_follow_up",
            consent_verified=False,
            policy_allowed=True,
            evidence_refs=("ledger:4",),
            idempotency_key="int-1",
        )


def test_outcome_and_knowledge_release_are_idempotent_and_auditable() -> None:
    service = RevenueIntelligenceService()
    signal = service.record_signal(
        tenant_key="ara-global",
        tenant_id="tenant-1",
        signal_type="expansion",
        subject_ref="account-9",
        confidence=0.95,
        evidence_refs=("usage:9",),
        evidence_hash="sha256:ghi",
        source="revenue-os",
        idempotency_key="sig-9",
    )
    intervention = service.propose_intervention(
        tenant_key="ara-global",
        signal_id=signal.id,
        action="recommend_review",
        consent_verified=True,
        policy_allowed=True,
        evidence_refs=("usage:9",),
        idempotency_key="int-9",
    )
    outcome = service.record_outcome(
        tenant_key="ara-global",
        intervention_id=intervention.id,
        status="accepted",
        evidence_refs=("human-review:9",),
        idempotency_key="out-9",
    )
    assert service.record_outcome(
        tenant_key="ara-global",
        intervention_id=intervention.id,
        status="accepted",
        evidence_refs=("human-review:9",),
        idempotency_key="out-9",
    ) == outcome

    release = service.publish_knowledge_release(
        tenant_key="ara-global",
        version="2026.08.10",
        source_refs=("kb:pricing", "kb:taxes"),
        content_hash="sha256:release",
        approved_by="user-1",
        idempotency_key="release-1",
    )
    assert release.status == "published"

    with pytest.raises(IdempotencyConflictError):
        service.publish_knowledge_release(
            tenant_key="ara-global",
            version="2026.08.11",
            source_refs=("kb:pricing",),
            content_hash="sha256:other",
            approved_by="user-1",
            idempotency_key="release-1",
        )
