# Phase 1 OIDC Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Authenticate users once through a configurable OIDC provider and project the same immutable identity into SignalLoop and CommitArc without centralizing application authorization.

**Architecture:** SignalLoop owns the suite identity projection and invitation lifecycle. Both applications validate Authorization Code + PKCE tokens against the configured issuer/JWKS and map `(issuer, subject)` to local users; local tenant memberships and entitlements remain authoritative. Password login stays enabled only behind an explicit local-development flag during rollout.

**Tech Stack:** FastAPI, SQLModel, Alembic, PyJWT, httpx, React, Next.js route handlers, Prisma, jose, Vitest, pytest, Playwright.

---

## File map

SignalLoop creates `app/domain/identity/{models,oidc,service,schemas}.py`, `app/api/routes/oidc.py`, one Alembic migration, API tests, and `apps/web/src/features/auth/OidcLoginButton.tsx`. CommitArc creates `src/server/auth/oidc.ts`, OIDC start/callback route handlers, one Prisma migration, and focused unit/e2e tests. Existing session and login files are modified only to introduce the OIDC-first switch and local authorization lookup.

### Task 1: Define the shared OIDC contract and SignalLoop identity projection

**Files:**
- Create: `apps/api/app/domain/identity/models.py`
- Create: `apps/api/app/domain/identity/schemas.py`
- Create: `apps/api/app/alembic/versions/p1_oidc_20260809_add_oidc_identity_projection.py`
- Modify: `apps/api/app/models.py`
- Test: `apps/api/tests/unit/test_oidc_identity_models.py`

- [ ] **Step 1: Write the failing model contract test**

```python
def test_oidc_identity_is_unique_per_issuer_subject(session):
    first = OidcIdentity(issuer="https://id.example.test", subject="user-1", user_id=user.id, email_snapshot="one@example.test")
    duplicate = OidcIdentity(issuer=first.issuer, subject=first.subject, user_id=other.id, email_snapshot="two@example.test")
    session.add(first)
    session.commit()
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.commit()
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_oidc_identity_models.py -q
```

Expected: collection fails because `OidcIdentity` does not exist.

- [ ] **Step 3: Add the exact persistence contract**

```python
class OidcIdentity(SQLModel, table=True):
    __tablename__ = "oidc_identity"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    issuer: str = Field(max_length=512)
    subject: str = Field(max_length=255)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    email_snapshot: str = Field(max_length=320)
    created_at: datetime = Field(default_factory=utc_now)
    last_login_at: datetime | None = None
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_oidc_identity_issuer_subject"),)
```

The migration also adds positive `auth_session_version` to `User`. It declares `revision = "p1_oidc_20260809"` and `down_revision = "tenant_20260809"`, creates the unique constraint and user foreign key, and stores no ID token, access token, refresh token, authorization code, or client secret. Before applying it, run `uv run alembic heads` from `apps/api` and require the single head `tenant_20260809`.

- [ ] **Step 4: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_oidc_identity_models.py -q
git add apps/api/app/domain/identity apps/api/app/models.py apps/api/app/alembic/versions/p1_oidc_20260809_add_oidc_identity_projection.py apps/api/tests/unit/test_oidc_identity_models.py
git commit -m "feat: add suite oidc identity projection"
```

Expected: test passes and the commit contains only the listed files.

### Task 2: Validate issuer metadata, state, nonce, PKCE, and claims in SignalLoop

**Files:**
- Modify: `apps/api/app/core/config.py`
- Create: `apps/api/app/domain/identity/oidc.py`
- Test: `apps/api/tests/unit/test_oidc_client.py`

- [ ] **Step 1: Write failing adversarial tests**

```python
@pytest.mark.anyio
@pytest.mark.parametrize("fault", ["state", "nonce", "issuer", "audience", "expired", "missing_sub"])
async def test_callback_rejects_invalid_oidc_response(fake_provider, fault):
    client = build_oidc_client(fake_provider.settings)
    response = fake_provider.callback_response(fault=fault)
    with pytest.raises(OidcValidationError):
        await client.exchange_and_validate(response)
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_oidc_client.py -q
```

Expected: tests fail because the OIDC client and configuration fields do not exist.

- [ ] **Step 3: Implement the minimal secure client**

Add `AUTH_MODE=oidc|local-test` and required OIDC-mode settings `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_AUDIENCE`, and `OIDC_SCOPES`; reject `local-test` when the environment is production. Derive endpoints from discovery; generate 32-byte state, nonce, and PKCE verifier. Store the original verifier plus state/nonce digests in a one-use server-side Redis transaction with a five-minute TTL; the HttpOnly, Secure, SameSite=Lax browser cookie carries only an opaque transaction ID. Fail closed when the transaction store is unavailable. Fetch JWKS through `httpx`; verify `RS256` signature, issuer, audience, expiry, nonce, and non-empty subject through PyJWT. Cache discovery/JWKS for at most one hour and retry once after an unknown `kid`.

- [ ] **Step 4: Run GREEN and commit**

```powershell
uv run --project apps/api pytest apps/api/tests/unit/test_oidc_client.py -q
uv run --project apps/api ruff check apps/api/app/domain/identity/oidc.py apps/api/tests/unit/test_oidc_client.py
git add apps/api/app/core/config.py apps/api/app/domain/identity/oidc.py apps/api/tests/unit/test_oidc_client.py
git commit -m "feat: validate oidc authorization flow"
```

### Task 3: Replace browser bearer storage with secure application-session cookies

**Files:**
- Modify: `apps/api/app/models.py`
- Create: `apps/api/app/alembic/versions/p1_session_20260809_secure_app_sessions.py`
- Modify: `apps/api/app/core/security.py`
- Modify: `apps/api/app/api/deps.py`
- Modify: `apps/api/app/api/routes/login.py`
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/hooks/useAuth.ts`
- Modify: `apps/web/src/lib/signalloop-api.ts`
- Modify: `apps/web/src/features/chatbot/api.ts`
- Test: `apps/api/tests/api/routes/test_login.py`
- Test: `apps/web/tests/login.spec.ts`

- [ ] **Step 1: Write failing cookie, CSRF, and storage tests**

```python
def test_login_uses_http_only_cookie_and_no_token_body(client, local_test_user):
    response = client.post("/api/v1/login/access-token", data=local_test_user.credentials)
    assert "access_token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]

def test_cookie_authenticated_mutation_requires_csrf(client, session_cookie):
    response = client.post("/api/v1/campaigns", cookies=session_cookie, json={})
    assert response.status_code == 403
```

The browser test asserts `localStorage.getItem("access_token")` is `null` after login and that logout clears the server session cookie.

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_login.py -q
npm --workspace frontend run test -- login.spec.ts
```

Expected: cookie/CSRF assertions fail and the browser still finds `access_token` in local storage.

- [ ] **Step 3: Implement the secure transport**

The migration declares `revision = "p1_session_20260809"`, `down_revision = "p1_oidc_20260809"`, and makes `User.hashed_password` nullable. Allow a password hash only in local-test mode. Put the signed short-lived app session token in an `HttpOnly; Secure; SameSite=Lax; Path=/` cookie, include `auth_session_version` and a digest of a separate random CSRF value, and recheck the live version plus memberships on every authorization dependency. Put the raw CSRF value in a Secure, SameSite=Lax non-HttpOnly cookie; require both its digest match and an allowlisted `Origin` on unsafe methods. Configure browser requests with credentials, remove bearer-token reads/writes from `main.tsx`, `useAuth.ts`, `signalloop-api.ts`, and chatbot API, and preserve only non-sensitive theme/demo preferences in local storage. Logout clears both cookies. Regenerate the OpenAPI client so no browser type expects an access token response body.

```python
def set_app_session(response: Response, token: str, csrf: str) -> None:
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="lax", path="/")
    response.set_cookie("csrf_token", csrf, httponly=False, secure=True, samesite="lax", path="/")
```

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_login.py -q
npm --workspace frontend run generate-client
npm --workspace frontend run test -- login.spec.ts
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/models.py apps/api/app/alembic/versions/p1_session_20260809_secure_app_sessions.py apps/api/app/core/security.py apps/api/app/api/deps.py apps/api/app/api/routes/login.py apps/api/app/core/config.py apps/api/tests/api/routes/test_login.py apps/web/src/main.tsx apps/web/src/hooks/useAuth.ts apps/web/src/lib/signalloop-api.ts apps/web/src/features/chatbot/api.ts apps/web/src/client apps/web/tests/login.spec.ts
git commit -m "fix: secure signalloop application sessions"
```

### Task 4: Add SignalLoop OIDC routes and local authorization resolution

**Files:**
- Create: `apps/api/app/domain/identity/service.py`
- Create: `apps/api/app/api/routes/oidc.py`
- Modify: `apps/api/app/api/main.py`
- Modify: `apps/api/app/api/deps.py`
- Modify: `apps/api/app/api/routes/login.py`
- Test: `apps/api/tests/api/routes/test_oidc.py`

- [ ] **Step 1: Write failing route tests**

```python
def test_callback_creates_session_only_for_invited_active_member(client, invited_identity):
    response = client.get("/api/v1/auth/oidc/callback?code=good&state=good", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].endswith("/home")
    assert "access_token=" in response.headers["set-cookie"]

def test_callback_denies_uninvited_subject(client, uninvited_identity):
    response = client.get("/api/v1/auth/oidc/callback?code=good&state=good")
    assert response.status_code == 403
```

- [ ] **Step 2: Run RED**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_oidc.py apps/api/tests/api/routes/test_login.py -q
```

Expected: route and invitation-acceptance assertions fail.

- [ ] **Step 3: Implement invitation-bound callback activation**

`GET /auth/oidc/start` resolves a verified tenant host or a cryptographically random one-use invitation token. It validates the invitation token digest, binds tenant ID, invitation ID, allowlisted relative return target, and host to the server-side OIDC transaction, then redirects. Localhost tests use explicit nonproduction domain rows and Secure-cookie override confined to the test server. `GET /auth/oidc/callback` validates the response and consumes that transaction exactly once. Existing identities must have an active suite membership for the bound tenant. Invitation acceptance requires a still-pending/unexpired tenant-bound invitation plus `email_verified=true` and an exact normalized match to the invitation address; that check validates the named invitation but never searches or links an existing user by email. In one database transaction it binds `(issuer, subject)`, activates the suite membership, marks the invitation accepted, increments projection version, and writes an outbox event for product projections. It updates `last_login_at`, then issues the SignalLoop session cookie with `auth_session_version`. `get_current_user` compares that version and reloads current memberships/entitlements from the database on each authorization boundary; token-carried roles are ignored. Session revocation increments the version. Password login returns `404` unless `AUTH_MODE=local-test`.

```python
class OidcTransaction(BaseModel):
    tenant_id: UUID
    invitation_id: UUID | None
    return_path: str
    state_digest: str
    nonce_digest: str
    pkce_verifier: str
```

- [ ] **Step 4: Run GREEN**

```powershell
uv run --project apps/api pytest apps/api/tests/api/routes/test_oidc.py apps/api/tests/api/routes/test_login.py -q
```

Expected: invited active users succeed; uninvited, suspended, wrong-tenant, and replayed state cases fail closed.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/domain/identity/service.py apps/api/app/api/routes/oidc.py apps/api/app/api/main.py apps/api/app/api/deps.py apps/api/app/api/routes/login.py apps/api/tests/api/routes/test_oidc.py apps/api/tests/api/routes/test_login.py
git commit -m "feat: add signalloop oidc login"
```

### Task 5: Add CommitArc OIDC identity mapping and callback

**Files:**
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\schema.prisma`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\prisma\migrations\20260809130000_add_oidc_identity\migration.sql`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\auth\oidc.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\auth\oidc\start\route.ts`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\api\auth\oidc\callback\route.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\auth\session.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\env.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\env.test.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\.env.example`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\server\auth\oidc.test.ts`

- [ ] **Step 1: Write failing claim and membership tests**

```typescript
it.each(["bad-state", "bad-nonce", "wrong-issuer", "wrong-audience", "expired"])(
  "rejects %s",
  async (fault) => expect(resolveOidcCallback(fakeCallback(fault))).rejects.toThrow(OidcError),
)

it("creates a session from the local active membership, not token roles", async () => {
  const session = await resolveOidcCallback(fakeCallback("token-claims-admin-local-membership-sales"))
  expect(session.role).toBe("SALES")
})
```

- [ ] **Step 2: Run RED**

```powershell
npm test -- src/server/auth/oidc.test.ts
```

Expected: missing module/schema failures.

- [ ] **Step 3: Implement the same issuer-subject contract**

Add a dedicated `UserIdentity` model with `id`, `userId`, `issuer`, `subject`, `emailSnapshot`, `createdAt`, `lastLoginAt`, `@@unique([issuer, subject])`, and an indexed user relation. Make `User.passwordHash` nullable; only `AUTH_MODE=local-test` users may have or use it, and production startup rejects local-test mode. Never match an OIDC login to an existing user by email alone. `src/server/env.ts` requires issuer, client ID, client secret, redirect URI, audience, and scopes in OIDC mode. Use `jose.createRemoteJWKSet` and `jwtVerify` with issuer, audience, expiry, and nonce checks. Resolve the local `OrganizationMembership`; reject missing, inactive, or suspended membership. Keep the current signed session shape and set its role/organization from local data.

- [ ] **Step 4: Run GREEN in eCRM**

```powershell
npx prisma validate
npx prisma generate
npm test -- src/server/auth/oidc.test.ts src/server/auth/session.test.ts src/server/organizations/context.test.ts
npm run typecheck
```

- [ ] **Step 5: Commit in eCRM**

```powershell
git add prisma/schema.prisma prisma/migrations/20260809130000_add_oidc_identity src/server/auth/oidc.ts src/app/api/auth/oidc src/server/auth/session.ts src/server/auth/oidc.test.ts src/server/env.ts src/server/env.test.ts .env.example
git commit -m "feat: add commit arc oidc login"
```

### Task 6: Replace both login entry points with OIDC-first behavior

**Files:**
- Create: `apps/web/src/features/auth/OidcLoginButton.tsx`
- Modify: `apps/web/src/routes/login.tsx`
- Modify: `apps/web/src/routes/signup.tsx`
- Modify: `apps/web/src/routes/recover-password.tsx`
- Modify: `apps/web/src/routes/reset-password.tsx`
- Test: `apps/web/tests/login.spec.ts`
- Modify: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\(auth)\login\login-form.tsx`
- Test: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\src\app\(auth)\login\login-form.test.tsx`
- Create: `C:\My Workspace\eCRM\.worktrees\enterprise-tenancy\tests\e2e\oidc-suite.spec.ts`

- [ ] **Step 1: Write failing browser assertions**

```typescript
await expect(page.getByRole("button", { name: "Continue with your work account" })).toBeVisible()
await expect(page.getByLabel("Password")).toBeHidden()
```

The e2e suite signs in once at the fake OIDC provider, enters SignalLoop, opens CommitArc, and proves the second application reuses the provider session without asking for credentials again.

- [ ] **Step 2: Run RED**

```powershell
npm --workspace frontend run test -- login.spec.ts
npm test -- 'src/app/(auth)/login/login-form.test.tsx'
npx playwright test tests/e2e/oidc-suite.spec.ts
```

Expected: OIDC-first and cross-application assertions fail.

- [ ] **Step 3: Implement OIDC-first entry behavior**

```typescript
export function OidcLoginButton() {
  return <button onClick={() => window.location.assign("/api/v1/auth/oidc/start")}>Continue with your work account</button>
}
```

In OIDC mode, signup is unavailable and recovery/reset redirect to the issuer recovery URL. In local-test mode, the existing local password controls remain visibly labeled as local development only. CommitArc follows the same mode rule without changing its generic landing content.

- [ ] **Step 4: Run GREEN**

```powershell
npm --workspace frontend run test -- login.spec.ts
npm test -- 'src/app/(auth)/login/login-form.test.tsx'
npx playwright test tests/e2e/oidc-suite.spec.ts
```

Expected: production-mode pages show only OIDC; local mode shows a clearly labeled local password fallback; cross-app navigation requires one credential entry.

- [ ] **Step 5: Commit separately in each repository**

Commit messages:

```text
feat: make signalloop login oidc first
feat: make commit arc login oidc first
```

### Task 7: Identity security and rollout gate

- [ ] Run SignalLoop API tests, ruff, mypy, frontend build, and login Playwright.
- [ ] Run CommitArc `npm run gate` plus OIDC Playwright.
- [ ] Verify logs contain no token, code, nonce, verifier, secret, or password values.
- [ ] Verify a disabled membership invalidates access on the next application authorization check without changing the OIDC account.
- [ ] Verify logout clears both application sessions; document that global IdP logout is provider-dependent and is not silently claimed.
