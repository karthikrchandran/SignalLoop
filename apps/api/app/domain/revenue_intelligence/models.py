"""Pure domain records for RevenueOS signals and interventions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RevenueSignal:
    tenant_key: str
    tenant_id: str
    signal_type: str
    subject_ref: str
    confidence: float
    evidence_refs: tuple[str, ...]
    evidence_hash: str
    source: str
    idempotency_key: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Intervention:
    tenant_key: str
    signal_id: UUID
    action: str
    consent_verified: bool
    policy_allowed: bool
    evidence_refs: tuple[str, ...]
    idempotency_key: str
    id: UUID = field(default_factory=uuid4)
    status: str = "proposed"
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Outcome:
    tenant_key: str
    intervention_id: UUID
    status: str
    evidence_refs: tuple[str, ...]
    idempotency_key: str
    id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class KnowledgeRelease:
    tenant_key: str
    version: str
    source_refs: tuple[str, ...]
    content_hash: str
    approved_by: str
    idempotency_key: str
    id: UUID = field(default_factory=uuid4)
    status: str = "published"
    released_at: datetime = field(default_factory=_now)
