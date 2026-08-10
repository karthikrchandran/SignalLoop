from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.identity.oidc import (
    OidcValidationError,
    build_pkce_challenge,
    normalize_issuer,
    validate_claims,
)


def _claims(**overrides: object) -> dict[str, object]:
    claims: dict[str, object] = {
        "iss": "https://id.example.test/",
        "aud": "client-123",
        "sub": "subject-1",
        "nonce": "nonce-1",
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
    }
    claims.update(overrides)
    return claims


def test_normalize_issuer_removes_trailing_slash() -> None:
    assert normalize_issuer("https://id.example.test/") == "https://id.example.test"


def test_pkce_challenge_is_deterministic_and_url_safe() -> None:
    verifier = "v" * 43
    assert build_pkce_challenge(verifier) == build_pkce_challenge(verifier)
    assert "+" not in build_pkce_challenge(verifier)
    assert "/" not in build_pkce_challenge(verifier)
    assert "=" not in build_pkce_challenge(verifier)


@pytest.mark.parametrize(
    "fault",
    ["state", "nonce", "issuer", "audience", "expired", "missing_sub"],
)
def test_validate_claims_rejects_adversarial_claims(fault: str) -> None:
    claims = _claims()
    expected = {
        "issuer": "https://id.example.test",
        "audience": "client-123",
        "nonce": "nonce-1",
    }
    if fault == "state":
        expected["nonce"] = "wrong-nonce"
    elif fault == "nonce":
        claims["nonce"] = "wrong-nonce"
    elif fault == "issuer":
        claims["iss"] = "https://attacker.example.test"
    elif fault == "audience":
        claims["aud"] = "other-client"
    elif fault == "expired":
        claims["exp"] = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
    elif fault == "missing_sub":
        claims.pop("sub")

    with pytest.raises(OidcValidationError):
        validate_claims(claims, **expected)


def test_validate_claims_returns_immutable_identity() -> None:
    identity = validate_claims(
        _claims(),
        issuer="https://id.example.test",
        audience="client-123",
        nonce="nonce-1",
    )
    assert identity.issuer == "https://id.example.test"
    assert identity.subject == "subject-1"
