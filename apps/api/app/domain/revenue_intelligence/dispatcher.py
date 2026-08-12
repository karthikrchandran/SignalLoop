"""Provider-bound execution for durable RevenueOS intervention dispatches."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .enforcement import (
    InterventionEnforcementDecision,
    PersistedSignalEnforcementGate,
)
from .persistence import RevenueInterventionStore
from .persistence_models import RevenueSignalRecord


@dataclass(frozen=True)
class InterventionDeliveryResult:
    """Normalized provider result used to settle a persisted dispatch."""

    provider: str
    accepted: bool
    retryable: bool
    receipt: dict[str, object]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class InterventionAttemptEnvelope:
    """Immutable provider command captured once per durable dispatch."""

    attempt_id: UUID
    intervention_id: UUID
    workspace_id: str
    channel: str
    destination_ref: str
    policy_decision_ref: str
    knowledge_release_refs: tuple[str, ...]
    idempotency_key: str
    scheduled_for: datetime
    action: str
    action_payload_json: str

    @property
    def payload(self) -> dict[str, object]:
        """Return a fresh payload copy; callers cannot mutate the stored command."""
        value = json.loads(self.action_payload_json)
        if not isinstance(value, dict):
            raise ValueError("attempt envelope payload must be an object")
        return value

    @classmethod
    def from_persisted(cls, value: dict[str, object]) -> InterventionAttemptEnvelope:
        return cls(
            attempt_id=UUID(str(value["attempt_id"])),
            intervention_id=UUID(str(value["intervention_id"])),
            workspace_id=str(value["workspace_id"]),
            channel=str(value["channel"]),
            destination_ref=str(value["destination_ref"]),
            policy_decision_ref=str(value["policy_decision_ref"]),
            knowledge_release_refs=tuple(str(item) for item in value["knowledge_release_refs"]),
            idempotency_key=str(value["idempotency_key"]),
            scheduled_for=datetime.fromisoformat(str(value["scheduled_for"])),
            action=str(value["action"]),
            action_payload_json=str(value["action_payload_json"]),
        )


class InterventionDelivery(Protocol):
    """Production provider seam; test doubles use the same contract."""

    async def deliver(
        self, *, envelope: InterventionAttemptEnvelope
    ) -> InterventionDeliveryResult:
        """Deliver one explicitly described intervention."""


class InterventionEnforcementGate(Protocol):
    """Policy boundary evaluated immediately before provider execution."""

    def evaluate(
        self,
        *,
        action: str,
        payload: dict[str, object],
        signal: RevenueSignalRecord,
    ) -> InterventionEnforcementDecision:
        """Return a current policy decision for this dispatch."""


class RevenueInterventionDispatcher:
    """Recheck policy gates immediately before execution, then settle durably."""

    def __init__(
        self,
        delivery: InterventionDelivery,
        *,
        enforcement_gate: InterventionEnforcementGate | None = None,
    ) -> None:
        self.delivery = delivery
        self.enforcement_gate = enforcement_gate or PersistedSignalEnforcementGate()

    async def dispatch(
        self,
        store: RevenueInterventionStore,
        *,
        tenant_id: UUID,
        dispatch_id: UUID,
        workspace_id: str,
    ) -> None:
        dispatch, intervention, signal = store.dispatch_context(
            tenant_id=tenant_id,
            dispatch_id=dispatch_id,
        )
        envelope = InterventionAttemptEnvelope.from_persisted(
            store.prepare_dispatch_attempt(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                workspace_id=workspace_id,
            )
        )
        decision = self.enforcement_gate.evaluate(
            action=envelope.action,
            payload=envelope.payload,
            signal=signal,
        )
        if not decision.allowed:
            store.record_dispatch_policy_block(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                reason=decision.reason or "POLICY_NOT_ALLOWED",
                next_attempt_at=decision.next_attempt_at,
            )
            return
        try:
            result = await self.delivery.deliver(
                envelope=envelope,
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
