"""Provider-bound execution for durable RevenueOS intervention dispatches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from .persistence import RevenueInterventionStore


@dataclass(frozen=True)
class InterventionDeliveryResult:
    """Normalized provider result used to settle a persisted dispatch."""

    provider: str
    accepted: bool
    retryable: bool
    receipt: dict[str, object]
    reason: str | None = None


class InterventionDelivery(Protocol):
    """Production provider seam; test doubles use the same contract."""

    async def deliver(
        self, *, action: str, payload: dict[str, object], idempotency_key: str
    ) -> InterventionDeliveryResult:
        """Deliver one explicitly described intervention."""


class RevenueInterventionDispatcher:
    """Recheck policy gates immediately before execution, then settle durably."""

    def __init__(self, delivery: InterventionDelivery) -> None:
        self.delivery = delivery

    async def dispatch(
        self, store: RevenueInterventionStore, *, tenant_id: UUID, dispatch_id: UUID
    ) -> None:
        dispatch, intervention, signal = store.dispatch_context(
            tenant_id=tenant_id,
            dispatch_id=dispatch_id,
        )
        if not signal.consent_verified:
            store.record_dispatch_failure(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                provider="policy-gate",
                reason="CONSENT_NOT_VERIFIED",
                retryable=False,
            )
            return
        if not signal.policy_allowed:
            store.record_dispatch_failure(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                provider="policy-gate",
                reason="POLICY_NOT_ALLOWED",
                retryable=False,
            )
            return
        try:
            result = await self.delivery.deliver(
                action=intervention.action,
                payload=intervention.action_payload,
                idempotency_key=str(dispatch.id),
            )
        except Exception as exc:  # provider boundary: transport faults are retryable
            store.record_dispatch_failure(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                provider="provider-transport",
                reason=f"TRANSPORT_{type(exc).__name__}",
                retryable=True,
            )
            return
        if result.accepted:
            store.record_dispatch_success(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                provider=result.provider,
                receipt=result.receipt,
            )
            return
        store.record_dispatch_failure(
            tenant_id=tenant_id,
            dispatch_id=dispatch.id,
            provider=result.provider,
            reason=result.reason or "PROVIDER_REJECTED",
            retryable=result.retryable,
        )
