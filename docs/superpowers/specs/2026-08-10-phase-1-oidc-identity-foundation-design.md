# Phase 1 OIDC Identity Foundation Design

## Goal

Authenticate a person once through a configured OIDC provider and resolve the same immutable identity in SignalLoop and CommitArc, while keeping tenant membership, product entitlement, and data authorization local to each application.

## Scope

This slice includes the identity projection, Authorization Code + PKCE validation, secure application sessions, session-version revocation, and the eCRM callback adapter. It does not include tenant provisioning, product entitlements, branding, RevenueOS behavior, CRM connectors, or provider dispatch changes.

## Non-negotiable security rules

- OIDC proves identity only; it never grants tenant or product access.
- The canonical external identity is `(issuer, subject)`. Email is a profile attribute and is never used for account matching.
- The PKCE verifier is retained only in a short-lived server-side transaction record or encrypted HttpOnly transaction cookie; only a digest of state and nonce is persisted.
- ID tokens, access tokens, refresh tokens, authorization codes, and client secrets are never stored in application tables.
- Callback state, nonce, issuer, audience, expiry, and required subject claims are validated before identity persistence.
- Sessions use secure HttpOnly cookies, SameSite protection, CSRF protection for state-changing routes, and explicit localhost test behavior.
- A positive session version is checked against the authoritative local user record on every session resolution. Revocation invalidates prior sessions without deleting identity history.
- Existing local password login remains available only behind an explicit local-development feature flag during rollout.
- Unknown, inactive, or uninvited identities fail closed without revealing whether a tenant or email exists.

## Components

### SignalLoop identity authority

SignalLoop owns the OIDC configuration, immutable identity projection, invitation activation, and suite session. It adds an `OidcIdentity` record keyed by `(issuer, subject)` and links it to the local user. The record stores only a normalized issuer, subject, email snapshot, timestamps, and the local user identifier.

### eCRM identity adapter

eCRM receives the verified identity result through its own callback/session adapter. It resolves a local user and active organization membership using the immutable identity mapping and local authorization tables. eCRM does not call the SignalLoop database and does not infer organization access from email.

### Session service

The session service issues an opaque session identifier in a secure HttpOnly cookie. Session state is server-side and contains the local user identifier, issuer/subject reference, issued time, expiry, and the session version observed at issuance. Every request resolves the current user, active membership, and current session version. A mismatch returns an unauthenticated result and clears the cookie.

## Authentication flow

1. The user selects Sign in with organization identity.
2. The app creates a short-lived authentication transaction bound to a verified application origin and optional signed invitation context.
3. The app redirects to the configured issuer using Authorization Code + PKCE, state, nonce, and the exact registered redirect URI.
4. The callback rejects missing, expired, reused, or mismatched transaction state before exchanging the code.
5. The server exchanges the code using the original PKCE verifier, validates issuer/audience/signature/nonce/expiry/subject, and normalizes the claims.
6. SignalLoop resolves an existing invitation or immutable identity binding. Email matching is not used as a fallback.
7. The server creates or updates the local identity projection, establishes the local session, and redirects only to an allowlisted relative return path.
8. Each application resolves local tenant memberships and product capabilities on demand.

## Invitation activation

An invitation carries a one-use digest, tenant binding, intended role bundle, expiry, and issuer context. The activation flow requires the signed invitation context plus a verified OIDC subject; it atomically marks the invitation accepted and creates the local membership projection. A second use, expired invitation, issuer mismatch, or tenant mismatch fails closed. OIDC group claims are informational only and cannot create authorization.

## Failure handling and observability

- Invalid state, nonce, PKCE, issuer, audience, subject, or expiry returns a generic authentication failure.
- Replayed transactions and invitations are rejected idempotently and audited.
- Session-version invalidation clears the local cookie and records a revocation event without exposing membership details.
- Audit entries contain actor identity reference, issuer, subject hash/reference, correlation ID, tenant context when known, and outcome; they never contain tokens or raw invitation secrets.
- Tests use a fake OIDC provider and fake clock. No external provider egress is allowed in acceptance tests.

## Verification gates

- Unit tests: identity uniqueness, issuer/subject normalization, claim validation, PKCE preservation, state/nonce replay, invitation activation, session version revocation, return-path safety.
- API tests: callback success, generic failure behavior, inactive membership denial, invitation one-use transition, local-password feature flag.
- eCRM contract tests: verified identity projection, organization membership resolution, cross-tenant denial, and session invalidation.
- Disposable PostgreSQL rehearsal: one Alembic head, migration upgrade from the current head, unique issuer/subject constraint, and rollback-safe session-version behavior.
- Browser acceptance: sign-in through the fake provider, successful redirect, logout, revoked-session denial, and no real provider network calls.

## Out of scope for this slice

- Platform administrator lifecycle and tenant/product entitlement APIs.
- Tenant branding, public tenant entry, and admin layouts.
- Native CommitArc projection delivery and reconciliation worker.
- RevenueOS signals, interventions, outcomes, and onboarding orchestration.
- CRM or campaign-management connectors.
