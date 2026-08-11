"""Persist immutable suite-to-product projection intents."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.domain.tenants.models import ProductInstallation, SuiteProjectionOutbox


class ProjectionConflict(ValueError):
    """Raised when an existing projection version has different content."""


class ProjectionTargetMismatch(ValueError):
    """Raised when an installation is not owned by the requested tenant."""


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def enqueue_projection(
    session: Session,
    *,
    tenant_id: UUID,
    installation_id: UUID,
    projection_kind: str,
    projection_version: int,
    payload: dict[str, Any],
) -> SuiteProjectionOutbox:
    """Persist one versioned projection without allowing conflicting retries."""
    installation = session.get(ProductInstallation, installation_id)
    if installation is None or installation.tenant_id != tenant_id:
        raise ProjectionTargetMismatch("installation does not belong to tenant")

    digest = hashlib.sha256(_canonical_payload(payload)).hexdigest()
    existing = session.exec(
        select(SuiteProjectionOutbox).where(
            SuiteProjectionOutbox.installation_id == installation_id,
            SuiteProjectionOutbox.projection_kind == projection_kind,
            SuiteProjectionOutbox.projection_version == projection_version,
        )
    ).one_or_none()
    if existing is not None:
        if existing.payload_digest != digest:
            raise ProjectionConflict("projection version already has a different payload")
        return existing

    projection = SuiteProjectionOutbox(
        tenant_id=tenant_id,
        installation_id=installation_id,
        projection_kind=projection_kind,
        projection_version=projection_version,
        payload=payload,
        payload_digest=digest,
    )
    session.add(projection)
    session.flush()
    return projection
