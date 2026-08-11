"""Restart-safe worker for cross-product suite projections."""

from __future__ import annotations

import base64
import binascii
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.domain.projections.dispatcher import (  # noqa: E402
    HttpxProjectionTransport,
    ProjectionDispatcher,
    claim_due_projections,
    recover_expired_projection_leases,
)

logger = logging.getLogger(__name__)

PROJECTION_POLL_INTERVAL_SECONDS = 30
PROJECTION_BATCH_SIZE = 100


class ProjectionWorkerConfigurationError(RuntimeError):
    """Raised when production signing material is not configured safely."""


def _private_key_from_base64(value: str) -> Ed25519PrivateKey:
    """Decode the 32-byte Ed25519 seed supplied by the deployment secret store."""
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ProjectionWorkerConfigurationError("invalid suite projection private key encoding") from exc
    if len(raw) != 32:
        raise ProjectionWorkerConfigurationError("suite projection private key must be a 32-byte Ed25519 seed")
    return Ed25519PrivateKey.from_private_bytes(raw)


def build_projection_dispatcher() -> ProjectionDispatcher:
    """Build the production dispatcher; there is intentionally no fake-key fallback."""
    if not settings.SUITE_PROJECTION_PRIVATE_KEY:
        raise ProjectionWorkerConfigurationError("suite projection private key is not configured")
    return ProjectionDispatcher(
        private_key=_private_key_from_base64(settings.SUITE_PROJECTION_PRIVATE_KEY),
        transport=HttpxProjectionTransport(),
    )


def process_claimed_projections(
    session: Session,
    dispatcher: ProjectionDispatcher,
    *,
    batch_size: int = PROJECTION_BATCH_SIZE,
) -> int:
    """Recover abandoned leases, claim due work, and settle every claimed row."""
    recovered = recover_expired_projection_leases(session)
    if recovered:
        logger.warning("Recovered %d expired projection lease(s)", recovered)
    projections = claim_due_projections(session, limit=batch_size)
    for projection in projections:
        dispatcher.dispatch(session, projection.id)
    return len(projections)


def process_projection_batch() -> int:
    """Execute one scheduled projection cycle against the production database."""
    dispatcher = build_projection_dispatcher()
    with Session(engine) as session:
        return process_claimed_projections(session, dispatcher)
