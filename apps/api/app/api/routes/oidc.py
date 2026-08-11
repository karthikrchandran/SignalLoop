"""OIDC authorization-code entry routes."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.api.deps import SessionDep
from app.api.routes.public_branding import verified_tenant_host
from app.core.config import settings
from app.domain.identity.models import OidcIdentity
from app.domain.identity.oidc import (
    OidcSubject,
    OidcValidationError,
    build_pkce_challenge,
    normalize_issuer,
    validate_claims,
)
from app.domain.identity.service import (
    OidcAuthorizationError,
    activate_oidc_identity,
    activate_oidc_identity_for_invitation,
)
from app.domain.identity.sessions import create_session
from app.domain.identity.transactions import OidcTransaction, OidcTransactionStore
from app.domain.tenants.models import Tenant, TenantInvitation

router = APIRouter(prefix="/auth/oidc", tags=["oidc"])


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _return_path(value: str | None) -> str:
    candidate = value or "/"
    if not candidate.startswith("/") or candidate.startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid return target")
    return candidate


def _require_oidc_settings() -> None:
    required = (
        settings.OIDC_ISSUER,
        settings.OIDC_CLIENT_ID,
        settings.OIDC_CLIENT_SECRET,
        settings.OIDC_REDIRECT_URI,
        settings.OIDC_AUDIENCE,
    )
    if settings.AUTH_MODE != "oidc" or not all(required):
        raise HTTPException(status_code=404, detail="OIDC login is unavailable")


def discover_oidc_configuration(issuer: str) -> dict[str, str]:
    """Load the provider discovery document without trusting caller endpoints."""
    try:
        response = httpx.get(
            f"{normalize_issuer(issuer)}/.well-known/openid-configuration", timeout=5.0
        )
        response.raise_for_status()
        configuration = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC provider is unavailable",
        ) from exc
    endpoint = configuration.get("authorization_endpoint")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC provider configuration is invalid",
        )
    return {"authorization_endpoint": endpoint}


def _transaction_store(request: Request) -> OidcTransactionStore:
    redis_manager = getattr(request.app.state, "redis_manager", None)
    redis = getattr(redis_manager, "client", None)
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC login is temporarily unavailable",
        )
    return OidcTransactionStore(redis, ttl_seconds=settings.OIDC_TRANSACTION_TTL_SECONDS)


async def exchange_and_validate(transaction: OidcTransaction, code: str) -> OidcSubject:
    """Exchange an authorization code and verify the issuer-signed ID token."""
    discovery_url = f"{normalize_issuer(transaction.issuer)}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            discovery_response = await client.get(discovery_url)
            discovery_response.raise_for_status()
            discovery = discovery_response.json()
            token_endpoint = discovery.get("token_endpoint")
            jwks_uri = discovery.get("jwks_uri")
            if not all(
                isinstance(endpoint, str) and endpoint.startswith("https://")
                for endpoint in (token_endpoint, jwks_uri)
            ):
                raise OidcValidationError("invalid provider configuration")
            token_response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.OIDC_CLIENT_ID,
                    "client_secret": settings.OIDC_CLIENT_SECRET,
                    "redirect_uri": settings.OIDC_REDIRECT_URI,
                    "code_verifier": transaction.pkce_verifier,
                },
            )
            token_response.raise_for_status()
            id_token = token_response.json().get("id_token")
            if not isinstance(id_token, str):
                raise OidcValidationError("missing ID token")
            kid = jwt.get_unverified_header(id_token).get("kid")
            jwks_response = await client.get(jwks_uri)
            jwks_response.raise_for_status()
    except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
        raise OidcValidationError("OIDC exchange failed") from exc

    key_data = next(
        (
            key
            for key in jwks_response.json().get("keys", [])
            if isinstance(key, dict) and key.get("kid") == kid and key.get("kty") == "RSA"
        ),
        None,
    )
    if key_data is None:
        raise OidcValidationError("signing key is unavailable")
    try:
        signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
        if not isinstance(signing_key, RSAPublicKey):
            raise OidcValidationError("signing key is invalid")
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            issuer=normalize_issuer(transaction.issuer),
            audience=settings.OIDC_AUDIENCE,
            options={"require": ["exp", "iss", "aud", "sub", "nonce"]},
        )
    except jwt.PyJWTError as exc:
        raise OidcValidationError("OIDC token is invalid") from exc
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(
        transaction.nonce_digest, _digest(nonce)
    ):
        raise OidcValidationError("nonce mismatch")
    return validate_claims(
        claims,
        issuer=transaction.issuer,
        audience=settings.OIDC_AUDIENCE,
        nonce=nonce,
    )


def _bound_tenant(
    request: Request, session: SessionDep, invitation_token: str | None
) -> tuple[Tenant, TenantInvitation | None]:
    invitation: TenantInvitation | None = None
    if invitation_token:
        invitation = session.exec(
            select(TenantInvitation).where(
                TenantInvitation.token_digest == _digest(invitation_token)
            )
        ).one_or_none()
        if invitation is None or invitation.status != "PENDING":
            raise HTTPException(status_code=404, detail="Workspace is not available")
        if invitation.expires_at is not None:
            expires_at = invitation.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(status_code=404, detail="Workspace is not available")
        tenant = session.get(Tenant, invitation.tenant_id)
        if tenant is None or tenant.status != "ACTIVE":
            raise HTTPException(status_code=404, detail="Workspace is not available")
        return tenant, invitation

    tenant_key = verified_tenant_host(request)
    tenant = (
        session.exec(select(Tenant).where(Tenant.key == tenant_key)).one_or_none()
        if tenant_key
        else None
    )
    if tenant is None or tenant.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Workspace is not available")
    return tenant, None


@router.get("/start")
async def start_oidc_login(
    request: Request,
    session: SessionDep,
    invitation_token: str | None = None,
    return_to: str | None = None,
) -> RedirectResponse:
    """Create one opaque server-side transaction and redirect to the issuer."""
    _require_oidc_settings()
    tenant, invitation = _bound_tenant(request, session, invitation_token)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    transaction_id = secrets.token_urlsafe(32)
    transaction = OidcTransaction(
        transaction_id=transaction_id,
        state_digest=_digest(state),
        nonce_digest=_digest(nonce),
        pkce_verifier=verifier,
        issuer=normalize_issuer(settings.OIDC_ISSUER),
        return_path=_return_path(return_to),
        tenant_id=str(tenant.id),
        invitation_id=str(invitation.id) if invitation else None,
    )
    await _transaction_store(request).put(transaction)
    endpoint = discover_oidc_configuration(settings.OIDC_ISSUER)["authorization_endpoint"]
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.OIDC_CLIENT_ID,
            "redirect_uri": settings.OIDC_REDIRECT_URI,
            "scope": settings.OIDC_SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": build_pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(f"{endpoint}?{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        "oidc_tx",
        transaction_id,
        httponly=True,
        secure=settings.ENVIRONMENT != "local",
        samesite="lax",
        path=f"{settings.API_V1_STR}/auth/oidc",
        max_age=settings.OIDC_TRANSACTION_TTL_SECONDS,
    )
    return response


@router.get("/callback")
async def complete_oidc_login(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
) -> RedirectResponse:
    """Consume one OIDC transaction and issue a local server-side session."""
    _require_oidc_settings()
    transaction_id = request.cookies.get("oidc_tx")
    if not transaction_id:
        raise HTTPException(status_code=400, detail="OIDC login transaction is invalid")
    transaction = await _transaction_store(request).consume(transaction_id)
    if (
        transaction is None
        or not hmac.compare_digest(transaction.state_digest, _digest(state))
        or transaction.tenant_id is None
    ):
        raise HTTPException(status_code=400, detail="OIDC login transaction is invalid")
    try:
        subject = await exchange_and_validate(transaction, code)
        tenant_id = UUID(transaction.tenant_id)
        known_identity = session.exec(
            select(OidcIdentity).where(
                OidcIdentity.issuer == subject.issuer,
                OidcIdentity.subject == subject.subject,
            )
        ).one_or_none()
        if known_identity is not None:
            user = activate_oidc_identity(
                session,
                tenant_id=tenant_id,
                invitation_token=None,
                issuer=subject.issuer,
                subject=subject.subject,
                email=subject.email,
                email_verified=subject.email_verified,
            )
        elif transaction.invitation_id is not None:
            user = activate_oidc_identity_for_invitation(
                session,
                tenant_id=tenant_id,
                invitation_id=UUID(transaction.invitation_id),
                issuer=subject.issuer,
                subject=subject.subject,
                email=subject.email,
                email_verified=subject.email_verified,
            )
        else:
            raise OidcAuthorizationError("identity is not authorized for this tenant")
        token = create_session(
            session,
            user=user,
            ttl=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        session.commit()
    except (OidcAuthorizationError, OidcValidationError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=403, detail="OIDC identity is not authorized") from exc

    response = RedirectResponse(
        transaction.return_path, status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.ENVIRONMENT != "local",
        samesite="lax",
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.delete_cookie("oidc_tx", path=f"{settings.API_V1_STR}/auth/oidc")
    return response
