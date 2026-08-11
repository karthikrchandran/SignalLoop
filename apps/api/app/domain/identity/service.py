"""Local authorization for verified OIDC identities."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.domain.identity.models import OidcIdentity
from app.domain.tenants.models import SuiteMembership, TenantInvitation
from app.models import User


class OidcAuthorizationError(ValueError):
    """Raised when an OIDC identity lacks local tenant authorization."""


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalized_email(value: str | None) -> str:
    if not value:
        raise OidcAuthorizationError("verified email is required")
    return value.strip().lower()


def _is_pending(invitation: TenantInvitation) -> bool:
    if invitation.status != "PENDING":
        return False
    if invitation.expires_at is None:
        return True
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)


def _active_membership(
    session: Session, *, user_id: UUID, tenant_id: UUID
) -> SuiteMembership | None:
    return session.exec(
        select(SuiteMembership).where(
            SuiteMembership.user_id == user_id,
            SuiteMembership.tenant_id == tenant_id,
            SuiteMembership.status == "ACTIVE",
        )
    ).one_or_none()


def _activate_new_identity(
    session: Session,
    *,
    tenant_id: UUID,
    invitation: TenantInvitation,
    issuer: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> User:
    if not email_verified:
        raise OidcAuthorizationError("verified email is required")
    normalized_email = _normalized_email(email)
    if not _is_pending(invitation) or _normalized_email(invitation.email) != normalized_email:
        raise OidcAuthorizationError("invitation is not valid for this identity")

    user = User(email=normalized_email, hashed_password="oidc-only")
    session.add(user)
    session.flush()
    session.add(
        OidcIdentity(
            issuer=issuer,
            subject=subject,
            user_id=user.id,
            email_snapshot=normalized_email,
            last_login_at=datetime.now(timezone.utc),
        )
    )
    session.add(SuiteMembership(tenant_id=tenant_id, user_id=user.id))
    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.now(timezone.utc)
    session.add(invitation)
    return user


def activate_oidc_identity(
    session: Session,
    *,
    tenant_id: UUID,
    invitation_token: str | None,
    issuer: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> User:
    """Authorize one verified issuer/subject pair for a tenant.

    Existing identities must already have an active local membership. New
    identities are created only through the named, pending invitation; this
    deliberately never searches for a user by email to link an identity.
    """
    identity = session.exec(
        select(OidcIdentity).where(
            OidcIdentity.issuer == issuer,
            OidcIdentity.subject == subject,
        )
    ).one_or_none()
    if identity is not None:
        user = session.get(User, identity.user_id)
        if user is None or not user.is_active or not _active_membership(
            session, user_id=user.id, tenant_id=tenant_id
        ):
            raise OidcAuthorizationError("identity is not authorized for this tenant")
        identity.last_login_at = datetime.now(timezone.utc)
        session.add(identity)
        return user

    if not invitation_token:
        raise OidcAuthorizationError("invitation is required")

    invitation = session.exec(
        select(TenantInvitation).where(
            TenantInvitation.tenant_id == tenant_id,
            TenantInvitation.token_digest == _token_digest(invitation_token),
        )
    ).one_or_none()
    if invitation is None:
        raise OidcAuthorizationError("invitation is not valid for this identity")
    return _activate_new_identity(
        session,
        tenant_id=tenant_id,
        invitation=invitation,
        issuer=issuer,
        subject=subject,
        email=email,
        email_verified=email_verified,
    )


def activate_oidc_identity_for_invitation(
    session: Session,
    *,
    tenant_id: UUID,
    invitation_id: UUID,
    issuer: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> User:
    """Activate a new identity through an invitation bound before redirecting."""
    invitation = session.get(TenantInvitation, invitation_id)
    if invitation is None or invitation.tenant_id != tenant_id:
        raise OidcAuthorizationError("invitation is not valid for this identity")
    return _activate_new_identity(
        session,
        tenant_id=tenant_id,
        invitation=invitation,
        issuer=issuer,
        subject=subject,
        email=email,
        email_verified=email_verified,
    )
