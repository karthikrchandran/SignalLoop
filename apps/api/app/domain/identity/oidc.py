"""OIDC protocol primitives shared by callback adapters."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class OidcValidationError(ValueError):
    """Raised when an OIDC response cannot be trusted."""


@dataclass(frozen=True)
class OidcSubject:
    issuer: str
    subject: str
    email: str | None


def normalize_issuer(issuer: str) -> str:
    normalized = issuer.strip().rstrip("/")
    if not normalized.startswith(("https://", "http://")):
        raise OidcValidationError("invalid issuer")
    return normalized


def build_pkce_challenge(verifier: str) -> str:
    if not verifier or len(verifier) < 43:
        raise OidcValidationError("invalid PKCE verifier")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _audience_matches(audience: Any, expected: str) -> bool:
    if isinstance(audience, str):
        return audience == expected
    return isinstance(audience, list) and expected in audience and all(
        isinstance(item, str) for item in audience
    )


def validate_claims(
    claims: dict[str, Any], *, issuer: str, audience: str, nonce: str
) -> OidcSubject:
    expected_issuer = normalize_issuer(issuer)
    actual_issuer = normalize_issuer(str(claims.get("iss", "")))
    if actual_issuer != expected_issuer:
        raise OidcValidationError("issuer mismatch")
    if not _audience_matches(claims.get("aud"), audience):
        raise OidcValidationError("audience mismatch")
    if claims.get("nonce") != nonce:
        raise OidcValidationError("nonce mismatch")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise OidcValidationError("subject missing")

    expiry = claims.get("exp")
    if not isinstance(expiry, int) or expiry <= int(datetime.now(timezone.utc).timestamp()):
        raise OidcValidationError("token expired")

    email = claims.get("email")
    if email is not None and not isinstance(email, str):
        raise OidcValidationError("invalid email claim")
    return OidcSubject(
        issuer=expected_issuer,
        subject=subject,
        email=email.strip().lower() if isinstance(email, str) else None,
    )
