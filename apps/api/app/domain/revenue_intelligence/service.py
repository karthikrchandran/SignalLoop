"""In-memory domain service; persistence adapters can be added without changing policy."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any, TypeVar, cast
from uuid import UUID

from .models import DispatchResult, Intervention, KnowledgeRelease, Outcome, RevenueSignal

T = TypeVar("T", RevenueSignal, Intervention, Outcome, KnowledgeRelease)


class EvidenceRequiredError(ValueError):
    """Raised when an auditable decision has no evidence."""


class TenantScopeError(ValueError):
    """Raised when a record is accessed from another tenant."""


class IdempotencyConflictError(ValueError):
    """Raised when a key is reused with a different request."""


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_evidence(refs: tuple[str, ...], evidence_hash: str | None = None) -> None:
    if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise EvidenceRequiredError("at least one evidence reference is required")
    if evidence_hash is not None and not evidence_hash.strip():
        raise EvidenceRequiredError("evidence hash is required")


class RevenueIntelligenceService:
    def __init__(self) -> None:
        self._signals: dict[UUID, RevenueSignal] = {}
        self._interventions: dict[UUID, Intervention] = {}
        self._outcomes: dict[UUID, Outcome] = {}
        self._releases: dict[UUID, KnowledgeRelease] = {}
        self._keys: dict[tuple[str, str], tuple[str, object]] = {}
        self._dispatch_keys: dict[tuple[str, str], DispatchResult] = {}

    def _idempotent(self, tenant_key: str, key: str, record: T) -> T:
        existing = self._keys.get((tenant_key, key))
        if existing is None:
            self._keys[(tenant_key, key)] = (type(record).__name__, record)
            return record
        kind, value = existing
        if kind != type(record).__name__ or self._fingerprint(value) != self._fingerprint(record):
            raise IdempotencyConflictError("idempotency key reused with different request")
        return value  # type: ignore[return-value]

    @staticmethod
    def _fingerprint(record: object) -> tuple[object, ...]:
        if not is_dataclass(record):
            raise TypeError("record must be a dataclass")
        return tuple(
            getattr(record, f.name)
            for f in fields(cast(Any, record))
            if f.name not in {"id", "created_at", "recorded_at", "released_at"}
        )

    def record_signal(self, *, tenant_key: str, tenant_id: str, signal_type: str, subject_ref: str, confidence: float, evidence_refs: tuple[str, ...], evidence_hash: str, source: str, idempotency_key: str) -> RevenueSignal:
        tenant_key, tenant_id = _require_text(tenant_key, "tenant_key"), _require_text(tenant_id, "tenant_id")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        _require_evidence(evidence_refs, evidence_hash)
        record = RevenueSignal(tenant_key, tenant_id, _require_text(signal_type, "signal_type"), _require_text(subject_ref, "subject_ref"), confidence, tuple(evidence_refs), evidence_hash.strip(), _require_text(source, "source"), _require_text(idempotency_key, "idempotency_key"))
        record = self._idempotent(tenant_key, record.idempotency_key, record)
        self._signals.setdefault(record.id, record)
        return record

    def propose_intervention(self, *, tenant_key: str, signal_id: UUID, action: str, consent_verified: bool, policy_allowed: bool, evidence_refs: tuple[str, ...], idempotency_key: str) -> Intervention:
        tenant_key = _require_text(tenant_key, "tenant_key")
        signal = self._signals.get(signal_id)
        if signal is None or signal.tenant_key != tenant_key:
            raise TenantScopeError("signal is not in tenant scope")
        if not consent_verified:
            raise ValueError("consent must be verified")
        if not policy_allowed:
            raise ValueError("policy decision must allow intervention")
        _require_evidence(evidence_refs)
        record = Intervention(tenant_key, signal_id, _require_text(action, "action"), consent_verified, policy_allowed, tuple(evidence_refs), _require_text(idempotency_key, "idempotency_key"))
        record = self._idempotent(tenant_key, record.idempotency_key, record)
        self._interventions.setdefault(record.id, record)
        return record

    def list_interventions(self, *, tenant_key: str) -> tuple[Intervention, ...]:
        tenant_key = _require_text(tenant_key, "tenant_key")
        return tuple(item for item in self._interventions.values() if item.tenant_key == tenant_key)

    def get_intervention(self, *, tenant_key: str, intervention_id: UUID) -> Intervention:
        item = self._interventions.get(intervention_id)
        if item is None or item.tenant_key != tenant_key:
            raise TenantScopeError("intervention is not in tenant scope")
        return item

    def transition_intervention(self, *, tenant_key: str, intervention_id: UUID, target: str, actor: str, idempotency_key: str) -> Intervention:
        item = self.get_intervention(tenant_key=tenant_key, intervention_id=intervention_id)
        _require_text(actor, "actor")
        _require_text(idempotency_key, "idempotency_key")
        allowed = {"proposed": {"approved", "rejected", "cancelled"}, "approved": {"cancelled", "dispatched"}, "dispatched": set()}
        if target not in allowed.get(item.status, set()):
            if item.status == target:
                return item
            raise ValueError(f"cannot transition intervention from {item.status} to {target}")
        updated = replace(item, status=target)
        self._interventions[item.id] = updated
        return updated

    def dispatch_approved(self, *, tenant_key: str, intervention_id: UUID, idempotency_key: str) -> DispatchResult:
        existing = self._dispatch_keys.get((tenant_key, idempotency_key))
        if existing is not None:
            if existing.intervention_id != intervention_id:
                raise IdempotencyConflictError("idempotency key reused with different intervention")
            return existing
        item = self.transition_intervention(tenant_key=tenant_key, intervention_id=intervention_id, target="dispatched", actor="fake-worker", idempotency_key=idempotency_key)
        result = DispatchResult(tenant_key, item.id, provider="fake", status="accepted")
        self._dispatch_keys[(tenant_key, idempotency_key)] = result
        return result

    def record_outcome(self, *, tenant_key: str, intervention_id: UUID, status: str, evidence_refs: tuple[str, ...], idempotency_key: str) -> Outcome:
        tenant_key = _require_text(tenant_key, "tenant_key")
        intervention = self._interventions.get(intervention_id)
        if intervention is None or intervention.tenant_key != tenant_key:
            raise TenantScopeError("intervention is not in tenant scope")
        _require_evidence(evidence_refs)
        record = Outcome(tenant_key, intervention_id, _require_text(status, "status"), tuple(evidence_refs), _require_text(idempotency_key, "idempotency_key"))
        record = self._idempotent(tenant_key, record.idempotency_key, record)
        self._outcomes.setdefault(record.id, record)
        return record

    def publish_knowledge_release(self, *, tenant_key: str, version: str, source_refs: tuple[str, ...], content_hash: str, approved_by: str, idempotency_key: str) -> KnowledgeRelease:
        tenant_key = _require_text(tenant_key, "tenant_key")
        _require_evidence(source_refs, content_hash)
        record = KnowledgeRelease(tenant_key, _require_text(version, "version"), tuple(source_refs), content_hash.strip(), _require_text(approved_by, "approved_by"), _require_text(idempotency_key, "idempotency_key"))
        record = self._idempotent(tenant_key, record.idempotency_key, record)
        self._releases.setdefault(record.id, record)
        return record
