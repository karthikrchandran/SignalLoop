"""Short-lived, tenant-bound EdDSA assertions between suite products."""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from collections.abc import Callable, MutableSet
from typing import Any, Literal, cast

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, Field


class WorkloadIdentityError(ValueError):
    """Raised whenever an installation assertion cannot be trusted."""


class WorkloadClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iss: Literal["commitarc", "revenueos", "signalloop"]
    aud: Literal["commitarc", "revenueos", "signalloop"]
    sub: uuid.UUID
    tenant_key: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=255)
    body_sha256: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    idempotency_key: str = Field(min_length=1, max_length=255)
    jti: uuid.UUID
    iat: int
    exp: int


def body_sha256(body: bytes) -> str:
    """Return the unpadded base64url SHA-256 digest of exact wire bytes."""

    return base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode("ascii")


def _key_bytes(key: Ed25519PrivateKey | Ed25519PublicKey | bytes) -> Ed25519PrivateKey | Ed25519PublicKey | bytes:
    return key


def create_workload_assertion(
    private_key: Ed25519PrivateKey | bytes,
    *,
    issuer: Literal["commitarc", "revenueos", "signalloop"],
    audience: Literal["commitarc", "revenueos", "signalloop"],
    installation_id: uuid.UUID,
    tenant_key: str,
    capability: str,
    body: bytes,
    idempotency_key: str,
    key_id: str,
    now: int | None = None,
    ttl_seconds: int = 120,
    jti: uuid.UUID | None = None,
) -> str:
    """Sign an assertion; lifetime is deliberately capped at two minutes."""

    if not 1 <= ttl_seconds <= 120:
        raise WorkloadIdentityError("assertion lifetime must be between one and 120 seconds")
    issued = int(time.time() if now is None else now)
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": str(installation_id),
        "tenant_key": tenant_key,
        "capability": capability,
        "body_sha256": body_sha256(body),
        "idempotency_key": idempotency_key,
        "jti": str(jti or uuid.uuid4()),
        "iat": issued,
        "exp": issued + ttl_seconds,
    }
    return jwt.encode(
        claims,
        cast(Any, _key_bytes(private_key)),
        algorithm="EdDSA",
        headers={"kid": key_id, "typ": "JWT"},
    )


class WorkloadVerifier:
    """Verify signature, time, tenant, endpoint, digest, and replay binding."""

    def __init__(
        self,
        public_key: Ed25519PublicKey | bytes,
        *,
        expected_issuer: Literal["commitarc", "revenueos", "signalloop"],
        expected_audience: Literal["commitarc", "revenueos", "signalloop"],
        replay_check: MutableSet[str] | Callable[[str], bool] | None = None,
        clock: Callable[[], int] | None = None,
        skew_seconds: int = 30,
    ) -> None:
        self.public_key = public_key
        self.expected_issuer = expected_issuer
        self.expected_audience = expected_audience
        self.replay_check = replay_check
        self.clock = clock or (lambda: int(time.time()))
        self.skew_seconds = skew_seconds

    def verify(
        self,
        token: str,
        *,
        installation_id: uuid.UUID,
        tenant_key: str,
        capability: str,
        body: bytes,
        idempotency_key: str,
        key_id: str,
    ) -> WorkloadClaims:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "EdDSA" or header.get("typ") != "JWT" or header.get("kid") != key_id:
                raise WorkloadIdentityError("invalid workload assertion header")
            decoded: dict[str, Any] = jwt.decode(
                token,
                cast(Any, _key_bytes(self.public_key)),
                algorithms=["EdDSA"],
                issuer=self.expected_issuer,
                audience=self.expected_audience,
                leeway=self.skew_seconds,
                options={"require": ["iss", "aud", "sub", "tenant_key", "capability", "body_sha256", "idempotency_key", "jti", "iat", "exp"]},
            )
            claims = WorkloadClaims.model_validate(decoded)
            now = self.clock()
            if claims.exp - claims.iat > 120 or claims.exp < now - self.skew_seconds or claims.iat > now + self.skew_seconds:
                raise WorkloadIdentityError("invalid workload assertion lifetime")
            if claims.sub != installation_id:
                raise WorkloadIdentityError("installation mismatch")
            if claims.tenant_key != tenant_key:
                raise WorkloadIdentityError("tenant mismatch")
            if claims.capability != capability:
                raise WorkloadIdentityError("capability mismatch")
            if claims.body_sha256 != body_sha256(body):
                raise WorkloadIdentityError("body digest mismatch")
            if claims.idempotency_key != idempotency_key:
                raise WorkloadIdentityError("idempotency mismatch")
            if self._replayed(str(claims.jti)):
                raise WorkloadIdentityError("replay detected")
            return claims
        except WorkloadIdentityError:
            raise
        except Exception as exc:
            raise WorkloadIdentityError("invalid workload assertion") from exc

    def _replayed(self, jti: str) -> bool:
        if self.replay_check is None:
            return False
        if callable(self.replay_check):
            return bool(self.replay_check(jti))
        if jti in self.replay_check:
            return True
        self.replay_check.add(jti)
        return False
