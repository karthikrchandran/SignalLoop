# Phase 1 Client Suite Tight Execution Backlog

> **For agentic workers:** Execute one work package at a time. Every package requires RED, GREEN, focused verification, review, and a scoped commit before the next dependent package begins.

**Goal:** Deliver centralized identity, tenant administration, independently entitled CommitArc/RevenueOS/SignalLoop experiences, and repeatable ARA Global and AI Consulting onboarding.

**Architecture:** SignalLoop is the suite identity/control-plane authority and RevenueOS host. CommitArc remains a separate database and authorization projection. OIDC proves identity; local memberships and entitlements authorize access. No third repository and no external CRM/campaign connectors in Phase 1.

**Baseline:** eCRM isolation, SignalLoop dispatch isolation, callback hardening, and date-sensitive report stabilization are complete. Preserve the pre-existing SignalLoop `apps/web/src/routeTree.gen.ts` change and eCRM `.tmp-pg-quality/`.

## Execution order

### WP1 — OIDC identity and secure sessions

Source plan: `docs/superpowers/plans/2026-08-09-phase-1-oidc-identity-plan.md`.

1. Add SignalLoop immutable `(issuer, subject)` identity projection and migration chained from `tenant_20260809`.
2. Add issuer/JWKS, state, nonce, PKCE, audience, expiry, and subject validation.
3. Add server-side session records, HttpOnly cookies, CSRF protection, and session-version revocation.
4. Add eCRM OIDC callback adapter and local membership resolution.
5. Keep password login only behind an explicit local-development flag.

Gate: fake-provider browser login succeeds in both products; revoked sessions fail; no token is persisted; all identity tests pass.

### WP2 — Platform control plane

Source plan: `docs/superpowers/plans/2026-08-09-phase-1-platform-control-plane-plan.md`.

1. Add tenants, product installations, entitlements, role bundles, memberships, invitations, and support grants.
2. Add platform-admin and tenant-admin guards with explicit data-plane denial.
3. Add audit records for provisioning, role changes, support grants, and revocations.

Gate: platform admin can provision but cannot read tenant data without an expiring audited grant; tenant admins cannot cross tenants.

### WP3 — Signed product projection and native integration

Source plans: `2026-08-09-phase-1-native-product-integration-plan.md` and the approved RevenueOS enterprise plan Tasks 8–10.

1. Add eCRM installation/key/replay-receipt projection.
2. Add signed membership/entitlement projection delivery with retry, dead-letter, acknowledgement, and reconciliation.
3. Add native CommitArc signal/writeback contracts and RevenueOS intervention/outcome records.

Gate: entitlement changes are idempotently projected; invalid signatures, stale versions, replayed events, and revoked installations fail closed.

### WP4 — Tenant branding and admin experiences

Source plans: `2026-08-09-phase-1-tenant-branding-admin-plan.md` and `2026-08-09-phase-1-unified-employee-experience-plan.md`.

1. Add verified tenant host/invitation resolution and immutable branding versions.
2. Add generic, ARA Global, and AI Consulting public entries.
3. Add platform-admin, tenant-admin, and role-specific employee shells.
4. Derive RevenueOS Essentials from active CommitArc membership; hide and deny unentitled features.

Gate: ARA and AI tenants render their own branding; unknown hosts disclose nothing; UI/API/worker/export permissions agree.

### WP5 — RevenueOS operating layer

Source plan: `2026-08-09-revenueos-enterprise-implementation-plan.md` Tasks 8–13.

1. Add knowledge-governed signals, interventions, outcomes, and evidence.
2. Enforce consent, budget, autonomy, policy, kill-switch, and idempotency gates.
3. Add separate ARA and AI Consulting configuration without inventing product capability, price, tax, contract, or payment-cycle answers.

Gate: every intervention is auditable, knowledge-grounded, consent-valid, and produces an outcome or explicit failure.

### WP6 — Onboarding and acceptance

Source plan: `2026-08-09-phase-1-onboarding-acceptance-plan.md`.

1. Add versioned onboarding manifest and idempotent provisioning stages.
2. Provision ARA Global and AI Consulting with all three products.
3. Keep HaloEHS unprovisioned.
4. Run fake email/SMS/chat/voice/scheduling providers with zero real egress.

Gate: repeated provisioning is safe; owner invitation, acceptance, canary, rollback, and evidence bundle all pass.

### WP7 — Release acceptance and handoff

1. Run both product browser suites with the same fake OIDC provider and tenant fixtures.
2. Run fresh PostgreSQL migration, projection, RLS, replay, and isolation rehearsals.
3. Run full scoped gates and compare against the recorded baseline.
4. Publish operator and client onboarding runbooks.

Gate: no new baseline failures, no browser console errors, no API 5xx, no provider egress, and clean scoped commits.

## Commit discipline

Each package is committed independently. Never stage `apps/web/src/routeTree.gen.ts`, `.tmp-pg-quality/`, generated client artifacts held by the live app, secrets, tokens, or customer data.
