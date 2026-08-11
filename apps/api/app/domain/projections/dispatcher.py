"""Durable, signed delivery of suite projections to product boundaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal, Protocol, cast
from uuid import UUID

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlmodel import Session, select

from app.domain.installations.workload_identity import create_workload_assertion
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    SuiteProjectionAttempt,
    SuiteProjectionOutbox,
    Tenant,
    utc_now,
)

PROJECTION_CAPABILITY = "suite.projections.write"


@dataclass(frozen=True)
class DeliveryResponse:
    """The minimal response contract required from a projection consumer."""

    status_code: int
    body: dict[str, Any]


class ProjectionTransport(Protocol):
    """HTTP boundary kept injectable for deterministic recovery tests."""

    def post(self, url: str, body: bytes, headers: dict[str, str]) -> DeliveryResponse:
        """Deliver a canonical projection envelope."""


class HttpxProjectionTransport:
    """Synchronous production transport used by the projection worker."""

    def post(self, url: str, body: bytes, headers: dict[str, str]) -> DeliveryResponse:
        response = httpx.post(url, content=body, headers=headers, timeout=15.0)
        try:
            response_body = response.json()
        except ValueError:
            response_body = {}
        return DeliveryResponse(status_code=response.status_code, body=response_body)


def _canonical_envelope(projection: SuiteProjectionOutbox, tenant: Tenant) -> bytes:
    return json.dumps(
        {
            "event_id": str(projection.event_id),
            "installation_id": str(projection.installation_id),
            "payload": projection.payload,
            "payload_digest": projection.payload_digest,
            "projection_kind": projection.projection_kind,
            "projection_version": projection.projection_version,
            "tenant_key": tenant.key,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(300, 10 * (2 ** max(0, attempt_count - 1))))


def _projection_audience(installation: ProductInstallation) -> Literal[
    "commitarc", "revenueos", "signalloop"
]:
    """Normalize the VARCHAR-backed product code before signing a strict claim."""
    return cast(
        Literal["commitarc", "revenueos", "signalloop"],
        ProductCode(installation.product_code).value,
    )


def claim_due_projections(
    session: Session, *, limit: int = 100, lease_seconds: int = 60
) -> list[SuiteProjectionOutbox]:
    """Lease due pending/retry rows so another worker cannot deliver them concurrently."""
    now = utc_now()
    rows = list(
        session.exec(
            select(SuiteProjectionOutbox)
            .where(
                SuiteProjectionOutbox.status.in_(("PENDING", "RETRY_SCHEDULED")),
                (SuiteProjectionOutbox.next_attempt_at.is_(None))
                | (SuiteProjectionOutbox.next_attempt_at <= now),
            )
            .order_by(SuiteProjectionOutbox.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
    )
    lease_expires_at = now + timedelta(seconds=lease_seconds)
    for row in rows:
        row.status = "IN_FLIGHT"
        row.lease_expires_at = lease_expires_at
        row.updated_at = now
        session.add(row)
    session.commit()
    return rows


def recover_expired_projection_leases(session: Session) -> int:
    """Return abandoned worker leases to pending state after a process crash."""
    now = utc_now()
    rows = list(
        session.exec(
            select(SuiteProjectionOutbox).where(
                SuiteProjectionOutbox.status == "IN_FLIGHT",
                SuiteProjectionOutbox.lease_expires_at <= now,
            )
        ).all()
    )
    for row in rows:
        row.status = "PENDING"
        row.lease_expires_at = None
        row.last_error = "WORKER_LEASE_EXPIRED"
        row.updated_at = now
        session.add(row)
    session.commit()
    return len(rows)


class ProjectionDispatcher:
    """Sign, deliver and durably settle one persisted projection at a time."""

    def __init__(
        self,
        *,
        private_key: Ed25519PrivateKey | bytes,
        transport: ProjectionTransport,
        max_attempts: int = 5,
    ) -> None:
        self.private_key = private_key
        self.transport = transport
        self.max_attempts = max_attempts

    def dispatch(self, session: Session, projection_id: UUID) -> SuiteProjectionOutbox:
        """Deliver a leased projection and persist every resulting state transition."""
        projection = session.get(SuiteProjectionOutbox, projection_id)
        if projection is None:
            raise ValueError("projection not found")
        if projection.status in {"ACKNOWLEDGED", "DEAD_LETTER"}:
            return projection

        installation = session.get(ProductInstallation, projection.installation_id)
        tenant = session.get(Tenant, projection.tenant_id)
        if installation is None or tenant is None or installation.tenant_id != tenant.id:
            return self._dead_letter(session, projection, "PROJECTION_TARGET_MISMATCH")
        if not installation.projection_endpoint:
            return self._configuration_blocked(session, projection, "PROJECTION_ENDPOINT_NOT_CONFIGURED")
        if not installation.workload_key_id:
            return self._configuration_blocked(session, projection, "WORKLOAD_KEY_NOT_CONFIGURED")

        body = _canonical_envelope(projection, tenant)
        assertion = create_workload_assertion(
            self.private_key,
            issuer="signalloop",
            audience=_projection_audience(installation),
            installation_id=installation.id,
            tenant_key=tenant.key,
            capability=PROJECTION_CAPABILITY,
            body=body,
            idempotency_key=str(projection.event_id),
            key_id=installation.workload_key_id,
        )
        try:
            response = self.transport.post(
                installation.projection_endpoint,
                body,
                {
                    "Authorization": f"Bearer {assertion}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": str(projection.event_id),
                    "X-Projection-Event-Id": str(projection.event_id),
                },
            )
        except (httpx.HTTPError, OSError) as exc:
            return self._retry_or_dead_letter(session, projection, f"TRANSPORT_{type(exc).__name__}")

        if 200 <= response.status_code < 300:
            if response.body.get("event_id") != str(projection.event_id):
                return self._dead_letter(session, projection, "INVALID_RECEIPT")
            projection.attempt_count += 1
            projection.status = "ACKNOWLEDGED"
            projection.acknowledgement_receipt = response.body
            projection.lease_expires_at = None
            projection.next_attempt_at = None
            projection.last_error = None
            projection.updated_at = utc_now()
            session.add(projection)
            self._record_attempt(
                session,
                projection,
                outcome="ACKNOWLEDGED",
                http_status=response.status_code,
            )
            session.commit()
            return projection
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            return self._retry_or_dead_letter(
                session,
                projection,
                f"HTTP_{response.status_code}",
                http_status=response.status_code,
            )
        return self._dead_letter(
            session,
            projection,
            f"HTTP_{response.status_code}",
            http_status=response.status_code,
        )

    def _configuration_blocked(
        self,
        session: Session,
        projection: SuiteProjectionOutbox,
        reason: str,
    ) -> SuiteProjectionOutbox:
        projection.status = "CONFIGURATION_BLOCKED"
        projection.lease_expires_at = None
        projection.last_error = reason
        projection.updated_at = utc_now()
        session.add(projection)
        self._record_attempt(session, projection, outcome="CONFIGURATION_BLOCKED", error_code=reason)
        session.commit()
        return projection

    def _retry_or_dead_letter(
        self,
        session: Session,
        projection: SuiteProjectionOutbox,
        reason: str,
        *,
        http_status: int | None = None,
    ) -> SuiteProjectionOutbox:
        projection.attempt_count += 1
        if projection.attempt_count >= self.max_attempts:
            return self._dead_letter(
                session,
                projection,
                reason,
                http_status=http_status,
                increment_attempt=False,
            )
        projection.status = "RETRY_SCHEDULED"
        projection.next_attempt_at = utc_now() + _retry_delay(projection.attempt_count)
        projection.lease_expires_at = None
        projection.last_error = reason
        projection.updated_at = utc_now()
        session.add(projection)
        self._record_attempt(
            session,
            projection,
            outcome="RETRY_SCHEDULED",
            http_status=http_status,
            error_code=reason,
        )
        session.commit()
        return projection

    def _dead_letter(
        self,
        session: Session,
        projection: SuiteProjectionOutbox,
        reason: str,
        *,
        http_status: int | None = None,
        increment_attempt: bool = True,
    ) -> SuiteProjectionOutbox:
        if increment_attempt:
            projection.attempt_count += 1
        projection.status = "DEAD_LETTER"
        projection.dead_letter_reason = reason
        projection.last_error = reason
        projection.lease_expires_at = None
        projection.next_attempt_at = None
        projection.updated_at = utc_now()
        session.add(projection)
        self._record_attempt(
            session,
            projection,
            outcome="DEAD_LETTER",
            http_status=http_status,
            error_code=reason,
        )
        session.commit()
        return projection

    @staticmethod
    def _record_attempt(
        session: Session,
        projection: SuiteProjectionOutbox,
        *,
        outcome: str,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        session.add(
            SuiteProjectionAttempt(
                projection_id=projection.id,
                attempt_number=max(1, projection.attempt_count),
                outcome=outcome,
                http_status=http_status,
                error_code=error_code,
            )
        )
