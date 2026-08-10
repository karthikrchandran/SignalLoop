"""Fake-safe RevenueOS intervention dispatcher for local and acceptance runs."""

from app.domain.revenue_intelligence.models import DispatchResult
from app.domain.revenue_intelligence.service import RevenueIntelligenceService


class InterventionWorker:
    def __init__(self, service: RevenueIntelligenceService) -> None:
        self.service = service

    def process(self, *, tenant_key: str, intervention_id, idempotency_key: str) -> DispatchResult:
        """Dispatch only through the fake adapter; no provider/network egress."""
        return self.service.dispatch_approved(tenant_key=tenant_key, intervention_id=intervention_id, idempotency_key=idempotency_key)
