from __future__ import annotations

import time
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.domain.installations.workload_identity import (
    WorkloadIdentityError,
    WorkloadVerifier,
    body_sha256,
    create_workload_assertion,
)


def test_body_digest_is_base64url_sha256_of_exact_bytes() -> None:
    assert body_sha256(b'{"a":1}') == "AVq9f1zFei3ZS3WQ8ErYCEJzkF7jPsXOvq5iJ2qX-GI"


def _signed(*, private: Ed25519PrivateKey, now: int | None = None, **overrides: object) -> str:
    kwargs: dict[str, object] = {
        "issuer": "signalloop",
        "audience": "revenueos",
        "installation_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "tenant_key": "ara-global",
        "capability": "revenue.signals.read",
        "body": b"hello",
        "idempotency_key": "idem-1",
        "key_id": "phase1-test-key-1",
        "now": now,
    }
    kwargs.update(overrides)
    return create_workload_assertion(private, **kwargs)  # type: ignore[arg-type]


def test_ed_dsa_assertion_round_trips_exact_claims() -> None:
    private = Ed25519PrivateKey.generate()
    token = _signed(private=private)
    claims = WorkloadVerifier(
        private.public_key(), expected_issuer="signalloop", expected_audience="revenueos"
    ).verify(
        token,
        installation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        tenant_key="ara-global",
        capability="revenue.signals.read",
        body=b"hello",
        idempotency_key="idem-1",
        key_id="phase1-test-key-1",
    )
    assert claims.tenant_key == "ara-global"
    assert claims.body_sha256 == body_sha256(b"hello")
    assert claims.jti


@pytest.mark.parametrize("fault", ["expired", "wrong_audience", "wrong_tenant", "wrong_digest"])
def test_assertion_fails_closed_for_claim_or_binding_fault(fault: str) -> None:
    private = Ed25519PrivateKey.generate()
    now = int(time.time())
    if fault == "expired":
        token = _signed(private=private, now=now - 180)
    elif fault == "wrong_audience":
        token = _signed(private=private, audience="commitarc")
    elif fault == "wrong_tenant":
        token = _signed(private=private, tenant_key="other-tenant")
    else:
        token = _signed(private=private)
    verifier = WorkloadVerifier(private.public_key(), expected_issuer="signalloop", expected_audience="revenueos")
    with pytest.raises(WorkloadIdentityError):
        verifier.verify(
            token,
            installation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            tenant_key="ara-global",
            capability="revenue.signals.read",
            body=b"different" if fault == "wrong_digest" else b"hello",
            idempotency_key="idem-1",
            key_id="phase1-test-key-1",
        )


def test_replayed_jti_is_rejected() -> None:
    private = Ed25519PrivateKey.generate()
    token = _signed(private=private)
    seen: set[str] = set()
    verifier = WorkloadVerifier(
        private.public_key(), expected_issuer="signalloop", expected_audience="revenueos", replay_check=seen
    )
    kwargs = {
        "installation_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "tenant_key": "ara-global",
        "capability": "revenue.signals.read",
        "body": b"hello",
        "idempotency_key": "idem-1",
        "key_id": "phase1-test-key-1",
    }
    verifier.verify(token, **kwargs)
    with pytest.raises(WorkloadIdentityError, match="replay"):
        verifier.verify(token, **kwargs)
