"""Transactional RevenueOS intervention lifecycle and recovery services."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.tenants.models import Tenant, utc_now

from .persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionRecord,
    RevenueSignalRecord,
)


class RevenueInterventionConflict(ValueError):
    """Raised when an idempotency key is reused with different business data."""


class RevenueInterventionNotFound(ValueError):
    """Raised when an intervention or signal is outside the tenant boundary."""


def _require_text(value: str, name: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_evidence(evidence_refs: list[str]) -> list[str]:
    if not evidence_refs or any(not ref.strip() for ref in evidence_refs):
        raise ValueError("at least one evidence reference is required")
    return [ref.strip() for ref in evidence_refs]


class RevenueInterventionStore:
    """Persist RevenueOS decisions instead of retaining process-local state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_signal(
        self,
        *,
        tenant_id: UUID,
        signal_type: str,
        subject_ref: str,
        confidence: float,
        evidence_refs: list[str],
        evidence_hash: str,
        source: str,
        consent_verified: bool,
        policy_allowed: bool,
        idempotency_key: str,
    ) -> RevenueSignalRecord:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        evidence = _require_evidence(evidence_refs)
        key = _require_text(idempotency_key, "idempotency_key")
        existing = self.session.exec(
            select(RevenueSignalRecord).where(
                RevenueSignalRecord.tenant_id == tenant_id,
                RevenueSignalRecord.idempotency_key == key,
            )
        ).one_or_none()
        candidate = (
            _require_text(signal_type, "signal_type"),
            _require_text(subject_ref, "subject_ref"),
            confidence,
            evidence,
            _require_text(evidence_hash, "evidence_hash"),
            _require_text(source, "source"),
            consent_verified,
            policy_allowed,
        )
        if existing is not None:
            current = (
                existing.signal_type,
                existing.subject_ref,
                existing.confidence,
                existing.evidence_refs,
                existing.evidence_hash,
                existing.source,
                existing.consent_verified,
                existing.policy_allowed,
            )
            if current != candidate:
                raise RevenueInterventionConflict("signal idempotency key conflicts with existing record")
            return existing
        signal = RevenueSignalRecord(
            tenant_id=tenant_id,
            signal_type=candidate[0],
            subject_ref=candidate[1],
            confidence=confidence,
            evidence_refs=evidence,
            evidence_hash=candidate[4],
            source=candidate[5],
            consent_verified=consent_verified,
            policy_allowed=policy_allowed,
            idempotency_key=key,
        )
        self.session.add(signal)
        self._audit(
            tenant_id=tenant_id,
            event_name="revenueos.signal.recorded",
            resource_type="revenue_signal",
            resource_id=str(signal.id),
            payload={
                "signal_type": signal.signal_type,
                "source": signal.source,
                "consent_verified": signal.consent_verified,
                "policy_allowed": signal.policy_allowed,
            },
        )
        self.session.commit()
        self.session.refresh(signal)
        return signal

    def propose_intervention(
        self,
        *,
        tenant_id: UUID,
        signal_id: UUID,
        action: str,
        action_payload: dict[str, object] | None = None,
        evidence_refs: list[str],
        idempotency_key: str,
    ) -> RevenueInterventionRecord:
        signal = self.session.exec(
            select(RevenueSignalRecord).where(
                RevenueSignalRecord.id == signal_id,
                RevenueSignalRecord.tenant_id == tenant_id,
            )
        ).one_or_none()
        if signal is None:
            raise RevenueInterventionNotFound("signal is not in tenant scope")
        evidence = _require_evidence(evidence_refs)
        action = _require_text(action, "action")
        payload = action_payload or {}
        key = _require_text(idempotency_key, "idempotency_key")
        existing = self.session.exec(
            select(RevenueInterventionRecord).where(
                RevenueInterventionRecord.tenant_id == tenant_id,
                RevenueInterventionRecord.idempotency_key == key,
            )
        ).one_or_none()
        if existing is not None:
            if (existing.signal_id, existing.action, existing.action_payload, existing.evidence_refs) != (
                signal_id,
                action,
                payload,
                evidence,
            ):
                raise RevenueInterventionConflict("intervention idempotency key conflicts with existing record")
            return existing
        denial_reason = None
        status = "PROPOSED"
        if not signal.consent_verified:
            status, denial_reason = "DENIED", "CONSENT_NOT_VERIFIED"
        elif not signal.policy_allowed:
            status, denial_reason = "DENIED", "POLICY_NOT_ALLOWED"
        intervention = RevenueInterventionRecord(
            tenant_id=tenant_id,
            signal_id=signal.id,
            action=action,
            action_payload=payload,
            evidence_refs=evidence,
            idempotency_key=key,
            status=status,
            denial_reason=denial_reason,
        )
        self.session.add(intervention)
        self._audit(
            tenant_id=tenant_id,
            event_name=(
                "revenueos.intervention.denied"
                if status == "DENIED"
                else "revenueos.intervention.proposed"
            ),
            resource_type="revenue_intervention",
            resource_id=str(intervention.id),
            payload={
                "signal_id": str(signal.id),
                "action": intervention.action,
                "status": status,
                "denial_reason": denial_reason,
            },
        )
        self.session.commit()
        self.session.refresh(intervention)
        return intervention

    def approve_intervention(
        self, *, tenant_id: UUID, intervention_id: UUID, actor_id: str
    ) -> RevenueInterventionRecord:
        intervention = self._intervention(tenant_id, intervention_id)
        if intervention.status == "APPROVED":
            return intervention
        if intervention.status != "PROPOSED":
            raise ValueError(f"cannot approve intervention in {intervention.status} state")
        intervention.status = "APPROVED"
        intervention.approved_by = _require_text(actor_id, "actor_id")
        intervention.approved_at = utc_now()
        intervention.updated_at = utc_now()
        self.session.add(intervention)
        self.session.add(
            RevenueInterventionDispatch(
                tenant_id=tenant_id,
                intervention_id=intervention.id,
            )
        )
        self._audit(
            tenant_id=tenant_id,
            event_name="revenueos.intervention.approved",
            resource_type="revenue_intervention",
            resource_id=str(intervention.id),
            payload={"actor_subject": intervention.approved_by, "dispatch_enqueued": True},
        )
        self.session.commit()
        self.session.refresh(intervention)
        return intervention

    def claim_due_dispatches(
        self, *, tenant_id: UUID, limit: int = 50, lease_seconds: int = 60
    ) -> list[RevenueInterventionDispatch]:
        now = utc_now()
        rows = list(
            self.session.exec(
                select(RevenueInterventionDispatch)
                .where(
                    RevenueInterventionDispatch.tenant_id == tenant_id,
                    RevenueInterventionDispatch.status.in_(("PENDING", "RETRY_SCHEDULED")),
                    (RevenueInterventionDispatch.next_attempt_at.is_(None))
                    | (RevenueInterventionDispatch.next_attempt_at <= now),
                )
                .order_by(RevenueInterventionDispatch.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        for dispatch in rows:
            dispatch.status = "IN_FLIGHT"
            dispatch.lease_expires_at = now + timedelta(seconds=lease_seconds)
            dispatch.updated_at = now
            self.session.add(dispatch)
            self._audit(
                tenant_id=tenant_id,
                event_name="revenueos.intervention.dispatch_claimed",
                resource_type="revenue_intervention_dispatch",
                resource_id=str(dispatch.id),
                payload={"intervention_id": str(dispatch.intervention_id)},
            )
        self.session.commit()
        return rows

    def recover_expired_dispatch_leases(self) -> int:
        now = utc_now()
        rows = list(
            self.session.exec(
                select(RevenueInterventionDispatch).where(
                    RevenueInterventionDispatch.status == "IN_FLIGHT",
                    RevenueInterventionDispatch.lease_expires_at <= now,
                )
            ).all()
        )
        for dispatch in rows:
            dispatch.status = "PENDING"
            dispatch.lease_expires_at = None
            dispatch.last_error = "WORKER_LEASE_EXPIRED"
            dispatch.updated_at = now
            self.session.add(dispatch)
            self._audit(
                tenant_id=dispatch.tenant_id,
                event_name="revenueos.intervention.dispatch_lease_recovered",
                resource_type="revenue_intervention_dispatch",
                resource_id=str(dispatch.id),
                payload={"intervention_id": str(dispatch.intervention_id)},
            )
        self.session.commit()
        return len(rows)

    def record_dispatch_success(
        self,
        *,
        tenant_id: UUID,
        dispatch_id: UUID,
        provider: str,
        receipt: dict[str, object],
    ) -> RevenueInterventionDispatch:
        """Settle an accepted provider delivery and mark its intervention dispatched."""
        dispatch = self._dispatch(tenant_id, dispatch_id)
        intervention = self._intervention(tenant_id, dispatch.intervention_id)
        dispatch.attempt_count += 1
        dispatch.status = "ACKNOWLEDGED"
        dispatch.provider = _require_text(provider, "provider")
        dispatch.provider_receipt = receipt
        dispatch.lease_expires_at = None
        dispatch.next_attempt_at = None
        dispatch.last_error = None
        dispatch.updated_at = utc_now()
        intervention.status = "DISPATCHED"
        intervention.updated_at = utc_now()
        self.session.add(dispatch)
        self.session.add(intervention)
        self._audit(
            tenant_id=tenant_id,
            event_name="revenueos.intervention.dispatch_acknowledged",
            resource_type="revenue_intervention_dispatch",
            resource_id=str(dispatch.id),
            payload={
                "intervention_id": str(intervention.id),
                "provider": dispatch.provider,
                "receipt": receipt,
            },
        )
        self.session.commit()
        self.session.refresh(dispatch)
        return dispatch

    def record_dispatch_failure(
        self,
        *,
        tenant_id: UUID,
        dispatch_id: UUID,
        provider: str,
        reason: str,
        retryable: bool,
        max_attempts: int = 5,
    ) -> RevenueInterventionDispatch:
        """Persist retry/backoff or dead-letter result without dropping evidence."""
        dispatch = self._dispatch(tenant_id, dispatch_id)
        intervention = self._intervention(tenant_id, dispatch.intervention_id)
        dispatch.attempt_count += 1
        dispatch.provider = _require_text(provider, "provider")
        dispatch.last_error = _require_text(reason, "reason")
        dispatch.lease_expires_at = None
        dispatch.updated_at = utc_now()
        if retryable and dispatch.attempt_count < max_attempts:
            dispatch.status = "RETRY_SCHEDULED"
            dispatch.next_attempt_at = utc_now() + _retry_delay(dispatch.attempt_count)
            event_name = "revenueos.intervention.dispatch_retry_scheduled"
        else:
            dispatch.status = "DEAD_LETTER"
            dispatch.dead_letter_reason = dispatch.last_error
            dispatch.next_attempt_at = None
            intervention.status = "DEAD_LETTER"
            intervention.updated_at = utc_now()
            self.session.add(intervention)
            event_name = "revenueos.intervention.dispatch_dead_lettered"
        self.session.add(dispatch)
        self._audit(
            tenant_id=tenant_id,
            event_name=event_name,
            resource_type="revenue_intervention_dispatch",
            resource_id=str(dispatch.id),
            payload={
                "intervention_id": str(intervention.id),
                "provider": dispatch.provider,
                "reason": dispatch.last_error,
                "attempt_count": dispatch.attempt_count,
            },
        )
        self.session.commit()
        self.session.refresh(dispatch)
        return dispatch

    def _intervention(self, tenant_id: UUID, intervention_id: UUID) -> RevenueInterventionRecord:
        intervention = self.session.exec(
            select(RevenueInterventionRecord).where(
                RevenueInterventionRecord.id == intervention_id,
                RevenueInterventionRecord.tenant_id == tenant_id,
            )
        ).one_or_none()
        if intervention is None:
            raise RevenueInterventionNotFound("intervention is not in tenant scope")
        return intervention

    def _dispatch(self, tenant_id: UUID, dispatch_id: UUID) -> RevenueInterventionDispatch:
        dispatch = self.session.exec(
            select(RevenueInterventionDispatch).where(
                RevenueInterventionDispatch.id == dispatch_id,
                RevenueInterventionDispatch.tenant_id == tenant_id,
            )
        ).one_or_none()
        if dispatch is None:
            raise RevenueInterventionNotFound("dispatch is not in tenant scope")
        return dispatch

    def dispatch_context(
        self, *, tenant_id: UUID, dispatch_id: UUID
    ) -> tuple[RevenueInterventionDispatch, RevenueInterventionRecord, RevenueSignalRecord]:
        """Return only an actively leased dispatch and its policy-gating signal."""
        dispatch = self._dispatch(tenant_id, dispatch_id)
        if dispatch.status != "IN_FLIGHT":
            raise ValueError(f"dispatch is not leased (state={dispatch.status})")
        intervention = self._intervention(tenant_id, dispatch.intervention_id)
        signal = self.session.exec(
            select(RevenueSignalRecord).where(
                RevenueSignalRecord.id == intervention.signal_id,
                RevenueSignalRecord.tenant_id == tenant_id,
            )
        ).one_or_none()
        if signal is None:
            raise RevenueInterventionNotFound("signal is not in tenant scope")
        return dispatch, intervention, signal

    def _audit(
        self,
        *,
        tenant_id: UUID,
        event_name: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, object],
    ) -> None:
        tenant = self.session.get(Tenant, tenant_id)
        if tenant is None:
            raise RevenueInterventionNotFound("tenant not found")
        append_audit_event_to_session(
            self.session,
            event_name=event_name,
            workspace_id=tenant.key,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
        )


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(300, 10 * (2 ** max(0, attempt_count - 1))))
