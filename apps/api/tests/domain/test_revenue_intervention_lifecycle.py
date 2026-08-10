from __future__ import annotations

import uuid

import pytest

from app.domain.revenue_intelligence.service import (
    RevenueIntelligenceService,
    TenantScopeError,
)


def _service() -> tuple[RevenueIntelligenceService, uuid.UUID]:
    service = RevenueIntelligenceService()
    signal = service.record_signal(
        tenant_key="ara-global", tenant_id="tenant-1", signal_type="risk",
        subject_ref="deal-1", confidence=0.9, evidence_refs=("event:1",),
        evidence_hash="sha256:1", source="revenue-os", idempotency_key="sig-1",
    )
    intervention = service.propose_intervention(
        tenant_key="ara-global", signal_id=signal.id, action="follow_up",
        consent_verified=True, policy_allowed=True, evidence_refs=("event:1",), idempotency_key="int-1",
    )
    return service, intervention.id


def test_intervention_transitions_and_fake_dispatch_are_idempotent() -> None:
    service, intervention_id = _service()
    approved = service.transition_intervention(tenant_key="ara-global", intervention_id=intervention_id, target="approved", actor="user-1", idempotency_key="approve-1")
    assert approved.status == "approved"
    result = service.dispatch_approved(tenant_key="ara-global", intervention_id=intervention_id, idempotency_key="dispatch-1")
    assert result.provider == "fake"
    assert service.get_intervention(tenant_key="ara-global", intervention_id=intervention_id).status == "dispatched"
    with pytest.raises(ValueError, match="cannot transition"):
        service.transition_intervention(tenant_key="ara-global", intervention_id=intervention_id, target="approved", actor="user-1", idempotency_key="approve-2")


def test_reject_and_cancel_are_terminal_and_tenant_scoped() -> None:
    service, intervention_id = _service()
    rejected = service.transition_intervention(tenant_key="ara-global", intervention_id=intervention_id, target="rejected", actor="user-1", idempotency_key="reject-1")
    assert rejected.status == "rejected"
    with pytest.raises(ValueError):
        service.transition_intervention(tenant_key="ara-global", intervention_id=intervention_id, target="cancelled", actor="user-1", idempotency_key="cancel-1")
    with pytest.raises(TenantScopeError):
        service.get_intervention(tenant_key="ai-consulting", intervention_id=intervention_id)
