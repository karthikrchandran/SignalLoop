# SignalLoop Provider Readiness Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the already-started provider readiness alignment so SignalLoop shows active provider selections, local-provider readiness, worker blockers, and callback status from one capability-aware setup surface.

**Architecture:** The backend `GET /api/v1/utils/setup-overview/` already returns capability-aware integration and worker readiness data. Keep that endpoint as the source of truth, extend the frontend API types once in `apps/web/src/lib/signalloop-api.ts`, then render the overview inside `apps/web/src/features/providers/ProviderSetupPage.tsx` and stop the legacy settings tab from implying fixed SendGrid/Twilio/Groq/Deepgram setup is the main path.

**Tech Stack:** FastAPI, SQLModel, React, TypeScript, TanStack Query, TanStack Router, Playwright, PowerShell.

---

## Sweep Findings

- Already implemented: Account Management backend/frontend files exist (`apps/api/app/api/routes/accounts.py`, `apps/web/src/features/customer-360/AccountFormDialog.tsx`, `apps/web/src/features/customer-360/AssignContactsDialog.tsx`) and recent git history includes `e809f35 Customer 360 account management`.
- Already implemented: the backend setup overview is capability-aware in `apps/api/app/api/routes/utils.py`, and tests cover local selections in `apps/api/tests/api/routes/test_utils.py` and `apps/api/tests/unit/test_setup_overview_provider_readiness.py`.
- Still incomplete: `apps/web/src/features/providers/ProviderSetupPage.tsx` only renders catalog/selections. It does not call `/api/v1/utils/setup-overview/`, show readiness blockers, show callback host state, or invalidate setup overview after provider selection changes.
- Still stale: `apps/web/src/routes/_layout/settings.tsx` has a `WorkspaceSetupTab` that looks up `sendgrid`, `twilio`, `deepgram`, and `groq` integration keys, but setup overview now returns capability keys such as `email`, `voice`, `stt`, `tts`, and `llm`.
- Still missing but lower priority: `docs/runbooks/` does not exist even though onboarding/user docs point to it. Do this after provider readiness because the open review backlog says provider readiness resolves immediate confusion.

## Execution Queue

1. Task 1: Add frontend setup overview API contract and tests.
2. Task 2: Render setup overview status on the Provider Setup page.
3. Task 3: Replace the stale Workspace setup tab content with a redirect-style handoff to Provider Setup plus health/callback summary.
4. Task 4: Run targeted gates and update the open review status note.

## File Structure

- Modify `apps/web/src/lib/signalloop-api.ts`: add setup overview TypeScript types and `getSetupOverview()`.
- Modify `apps/web/src/features/providers/ProviderSetupPage.tsx`: fetch setup overview, render capability readiness, worker readiness, callback host, and refresh it after provider changes.
- Modify `apps/web/src/routes/_layout/settings.tsx`: remove fixed SendGrid/Twilio/Groq/Deepgram credential editor emphasis from the settings tab and point provider-specific setup to `/settings/providers`.
- Modify `apps/web/tests/provider-setup.spec.ts`: add mocked setup-overview responses and assertions for readiness, local providers, worker blockers, and callback host warnings.
- Modify `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`: mark backend setup overview as already complete and frontend setup page alignment as completed by this slice.

---

## Task 1: Frontend Setup Overview API Contract

**Files:**
- Modify: `apps/web/src/lib/signalloop-api.ts`
- Modify: `apps/web/tests/provider-setup.spec.ts`

- [ ] **Step 1: Add failing Playwright coverage for setup overview fetch**

Append this helper and test data to `apps/web/tests/provider-setup.spec.ts` after `providerOptions`:

```ts
const setupOverview = {
  workspace_id: "default",
  health: {
    api: true,
    postgres: true,
    redis: true,
  },
  integrations: [
    {
      key: "email",
      label: "EMAIL: Generic SMTP / Mailpit",
      configured: true,
      source: "environment",
      editable: true,
      has_secret: false,
      config: { host: "localhost", port: "1025", from_email: "demo@example.com" },
      note: "Email delivery uses the selected SMTP relay or local mail catcher.",
      capability: "email",
      provider: "smtp",
      provider_label: "Generic SMTP / Mailpit",
      requires_creds: false,
      local: true,
    },
    {
      key: "voice",
      label: "VOICE: Vapi AI Voice",
      configured: false,
      source: "missing",
      editable: true,
      has_secret: false,
      config: {},
      note: "Voice calls use the selected Vapi assistant and Vapi phone number.",
      capability: "voice",
      provider: "vapi",
      provider_label: "Vapi AI Voice",
      requires_creds: true,
      local: false,
    },
    {
      key: "stt",
      label: "STT: Faster Whisper Local",
      configured: true,
      source: "environment",
      editable: true,
      has_secret: false,
      config: { base_url: "http://localhost:9000", model: "base" },
      note: "Local batch transcription is configured; live voice streaming still needs a streaming STT provider.",
      capability: "stt",
      provider: "faster_whisper_local",
      provider_label: "Faster Whisper Local",
      requires_creds: false,
      local: true,
    },
    {
      key: "llm",
      label: "LLM: Ollama",
      configured: true,
      source: "environment",
      editable: true,
      has_secret: false,
      config: { base_url: "http://localhost:11434", model: "llama3.2:1b" },
      note: "LLM responses use the configured local Ollama endpoint.",
      capability: "llm",
      provider: "ollama_local",
      provider_label: "Ollama",
      requires_creds: false,
      local: true,
    },
  ],
  worker_readiness: [
    {
      key: "sequence_worker",
      label: "Sequence worker",
      ready: true,
      running: true,
      status: "healthy",
      last_seen_at: "2026-06-15T12:00:00Z",
      last_error_message: null,
      missing: [],
    },
    {
      key: "call_worker",
      label: "Call worker",
      ready: false,
      running: false,
      status: "not_seen",
      last_seen_at: null,
      last_error_message: null,
      missing: ["voice_provider", "tts_provider", "public_callbacks"],
    },
  ],
  callbacks: {
    server_host: "localhost:8001",
    public_base_url: "http://localhost:8001",
    public_host: false,
    sendgrid_webhook_url: "http://localhost:8001/api/v1/webhooks/sendgrid",
    twilio_twiml_url: "http://localhost:8001/api/v1/voice/twiml",
    twilio_status_url: "http://localhost:8001/api/v1/voice/status",
    twilio_recording_url: "http://localhost:8001/api/v1/voice/recording",
    twilio_media_stream_url: "ws://localhost:8001/api/v1/voice/media-stream",
  },
}
```

Update `mockProviderEndpoints()` to also route setup overview:

```ts
  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(setupOverview),
    })
  })
```

Add this test:

```ts
test("renders setup overview readiness from capability-aware endpoint", async ({ page }) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(page.getByTestId("provider-card-email")).toContainText("Ready")
  await expect(page.getByTestId("provider-card-email")).toContainText("localhost")
  await expect(page.getByTestId("provider-card-voice")).toContainText("Missing setup")
  await expect(page.getByTestId("provider-worker-readiness")).toContainText("Call worker")
  await expect(page.getByTestId("provider-worker-readiness")).toContainText("voice provider")
  await expect(page.getByTestId("provider-callback-status")).toContainText("Local only")
})
```

- [ ] **Step 2: Run the failing frontend test**

Run:

```powershell
cd apps\web
npx playwright test tests/provider-setup.spec.ts --project=chromium --reporter=line
```

Expected: the new test fails because `ProviderSetupPage` does not call setup overview or render `provider-worker-readiness` / `provider-callback-status`.

- [ ] **Step 3: Add setup overview types and client function**

In `apps/web/src/lib/signalloop-api.ts`, add these exports after `ProviderSelectionsPublic`:

```ts
export type SetupIntegration = {
  key: string
  label: string
  configured: boolean
  source: string
  editable: boolean
  has_secret: boolean
  config: Record<string, string>
  note?: string | null
  capability?: ProviderCapability | null
  provider?: string | null
  provider_label?: string | null
  requires_creds?: boolean | null
  local?: boolean | null
}

export type SetupWorkerReadiness = {
  key: string
  label: string
  ready: boolean
  running: boolean
  status: string
  last_seen_at?: string | null
  last_error_message?: string | null
  missing: string[]
}

export type SetupOverview = {
  workspace_id: string
  health: {
    api: boolean
    postgres: boolean
    redis: boolean
  }
  integrations: SetupIntegration[]
  worker_readiness: SetupWorkerReadiness[]
  callbacks: {
    server_host: string
    public_base_url: string
    public_host: boolean
    sendgrid_webhook_url: string
    twilio_twiml_url: string
    twilio_status_url: string
    twilio_recording_url: string
    twilio_media_stream_url: string
  }
}
```

Add this function after `getProviderSelections()`:

```ts
export function getSetupOverview(workspaceId = getWorkspaceId()) {
  return signalloopRequest<SetupOverview>("/api/v1/utils/setup-overview/", {
    workspaceId,
  })
}
```

- [ ] **Step 4: Run TypeScript check for the API client**

Run:

```powershell
cd apps\web
npx tsc --noEmit
```

Expected: TypeScript still fails only because `ProviderSetupPage` has not used the new function yet, or passes if no unused export rule exists.

Do not commit yet. Task 2 consumes this API function.

---

## Task 2: Provider Setup Readiness Rendering

**Files:**
- Modify: `apps/web/src/features/providers/ProviderSetupPage.tsx`
- Modify: `apps/web/tests/provider-setup.spec.ts`

- [ ] **Step 1: Import overview API and status icons**

In `apps/web/src/features/providers/ProviderSetupPage.tsx`, change the imports:

```ts
import { CheckCircle2, Loader2, RefreshCw, ServerCog, TriangleAlert } from "lucide-react"
```

Extend the API imports:

```ts
  type SetupIntegration,
  type SetupWorkerReadiness,
  getSetupOverview,
```

- [ ] **Step 2: Fetch setup overview and invalidate it after provider selection**

Inside `ProviderSetupPage()`, add:

```ts
  const overviewQuery = useQuery({
    queryKey: ["setup-overview", workspaceId],
    queryFn: () => getSetupOverview(workspaceId),
  })
```

In the `onSuccess` handler for `updateSelection`, add:

```ts
      await queryClient.invalidateQueries({
        queryKey: ["setup-overview", workspaceId],
      })
```

In the Refresh button `onClick`, add:

```ts
              overviewQuery.refetch()
```

Extend the disabled state:

```ts
            disabled={
              optionsQuery.isFetching ||
              selectionsQuery.isFetching ||
              overviewQuery.isFetching
            }
```

- [ ] **Step 3: Build an overview map by capability**

After `selectionsByCapability`, add:

```ts
  const integrationsByCapability = useMemo(() => {
    const entries = overviewQuery.data?.integrations ?? []
    return new Map(
      entries
        .filter((entry) => entry.capability)
        .map((entry) => [entry.capability as ProviderCapability, entry]),
    )
  }, [overviewQuery.data?.integrations])
```

When rendering `CapabilityCard`, pass:

```tsx
              integration={integrationsByCapability.get(entry.capability)}
```

- [ ] **Step 4: Render health, workers, and callback summary**

Before the provider card grid, add:

```tsx
          {overviewQuery.data && (
            <div className="grid gap-4 lg:grid-cols-3">
              <ReadinessSummaryCard
                title="Core services"
                items={[
                  { label: "API", ready: overviewQuery.data.health.api },
                  { label: "Postgres", ready: overviewQuery.data.health.postgres },
                  { label: "Redis", ready: overviewQuery.data.health.redis },
                ]}
              />
              <WorkerReadinessCard workers={overviewQuery.data.worker_readiness} />
              <CallbackStatusCard overview={overviewQuery.data} />
            </div>
          )}
```

Add helper components at the bottom of the file before `providerLabel()`:

```tsx
function ReadinessSummaryCard({
  title,
  items,
}: {
  title: string
  items: Array<{ label: string; ready: boolean }>
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>Live readiness reported by the API.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
            <span className="font-medium">{item.label}</span>
            <ReadinessBadge ready={item.ready} />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function WorkerReadinessCard({ workers }: { workers: SetupWorkerReadiness[] }) {
  return (
    <Card data-testid="provider-worker-readiness">
      <CardHeader>
        <CardTitle className="text-base">Workers</CardTitle>
        <CardDescription>Background worker readiness for selected providers.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {workers.map((worker) => (
          <div key={worker.key} className="rounded-md border p-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">{worker.label}</span>
              <ReadinessBadge ready={worker.ready} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {worker.ready ? "Running with required providers." : formatMissing(worker.missing)}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function CallbackStatusCard({ overview }: { overview: import("@/lib/signalloop-api").SetupOverview }) {
  return (
    <Card data-testid="provider-callback-status">
      <CardHeader>
        <CardTitle className="text-base">Callback host</CardTitle>
        <CardDescription>Provider webhooks use this external base URL.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between gap-3 rounded-md border p-3">
          <span className="font-medium">Base URL</span>
          <Badge className={overview.callbacks.public_host ? "bg-emerald-100 text-emerald-900 hover:bg-emerald-100" : "bg-amber-100 text-amber-900 hover:bg-amber-100"}>
            {overview.callbacks.public_host ? "Public" : "Local only"}
          </Badge>
        </div>
        <p className="break-all text-muted-foreground">{overview.callbacks.public_base_url}</p>
      </CardContent>
    </Card>
  )
}

function ReadinessBadge({ ready }: { ready: boolean }) {
  return ready ? (
    <Badge className="gap-1 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">
      <CheckCircle2 className="size-3" />
      Ready
    </Badge>
  ) : (
    <Badge className="gap-1 bg-amber-100 text-amber-900 hover:bg-amber-100">
      <TriangleAlert className="size-3" />
      Missing setup
    </Badge>
  )
}

function formatMissing(missing: string[]) {
  if (missing.length === 0) {
    return "Waiting for worker heartbeat."
  }
  return `Missing: ${missing.map((item) => item.replaceAll("_", " ")).join(", ")}.`
}
```

- [ ] **Step 5: Render per-capability integration details**

Update `CapabilityCard` props:

```ts
  integration?: SetupIntegration
```

Update the function signature to receive `integration`.

Inside `CapabilityCard`, after `selectedOption?.free_tier`, add:

```tsx
          {integration && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{integration.provider_label ?? integration.label}</span>
                <ReadinessBadge ready={integration.configured} />
              </div>
              {Object.entries(integration.config).length > 0 && (
                <dl className="mt-3 space-y-1 text-xs text-muted-foreground">
                  {Object.entries(integration.config).map(([key, value]) => (
                    <div key={key} className="flex items-start justify-between gap-3">
                      <dt className="font-medium text-foreground">{key.replaceAll("_", " ")}</dt>
                      <dd className="break-all text-right">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {integration.note && (
                <p className="mt-2 text-xs text-muted-foreground">{integration.note}</p>
              )}
            </div>
          )}
```

- [ ] **Step 6: Run the focused Playwright test**

Run:

```powershell
cd apps\web
npx playwright test tests/provider-setup.spec.ts --project=chromium --reporter=line
```

Expected: all provider setup tests pass, including the new setup overview readiness test.

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add apps/web/src/lib/signalloop-api.ts apps/web/src/features/providers/ProviderSetupPage.tsx apps/web/tests/provider-setup.spec.ts
git commit -m "feat: show provider readiness overview"
```

---

## Task 3: Settings Workspace Setup Handoff

**Files:**
- Modify: `apps/web/src/routes/_layout/settings.tsx`
- Modify: `apps/web/tests/provider-setup.spec.ts`

- [ ] **Step 1: Add route assertion for Provider Setup as the canonical provider surface**

Append this test to `apps/web/tests/provider-setup.spec.ts`:

```ts
test("provider setup remains the canonical provider readiness route", async ({ page }) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(page.getByRole("heading", { name: "Provider Setup" })).toBeVisible()
  await expect(page.getByTestId("provider-worker-readiness")).toBeVisible()
  await expect(page.getByTestId("provider-callback-status")).toBeVisible()
})
```

- [ ] **Step 2: Remove stale fixed-provider integration lookups**

In `apps/web/src/routes/_layout/settings.tsx`, remove these constants:

```ts
  const sendgrid = integrationMap.get("sendgrid")
  const twilio = integrationMap.get("twilio")
  const deepgram = integrationMap.get("deepgram")
  const groq = integrationMap.get("groq")
```

Replace them with:

```ts
  const email = integrationMap.get("email")
  const voice = integrationMap.get("voice")
  const stt = integrationMap.get("stt")
  const tts = integrationMap.get("tts")
  const llm = integrationMap.get("llm")
```

- [ ] **Step 3: Replace fixed credential cards with a provider setup handoff**

In `WorkspaceSetupTab`, replace the two-card grid containing `CredentialEditorCard` for SendGrid and Twilio Voice with:

```tsx
          <Card>
            <CardHeader>
              <CardTitle>Provider readiness</CardTitle>
              <CardDescription>
                Provider selection and per-capability readiness now live in the dedicated Provider Setup page.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                {[email, voice, stt, tts, llm].filter(Boolean).map((integration) => (
                  <div key={integration?.key} className="rounded-lg border p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h3 className="font-medium">{integration?.label}</h3>
                        <p className="text-xs text-muted-foreground">Source: {integration?.source}</p>
                      </div>
                      <StatusBadge ready={integration?.configured ?? false} />
                    </div>
                    {integration?.note && (
                      <p className="mt-3 text-sm text-muted-foreground">{integration.note}</p>
                    )}
                  </div>
                ))}
              </div>
              <Button asChild>
                <a href="/settings/providers">Open Provider Setup</a>
              </Button>
            </CardContent>
          </Card>
```

Do not remove `CredentialEditorCard` yet if other parts of this file still reference it; after the replacement, run TypeScript and remove unused functions/imports only when the compiler reports them.

- [ ] **Step 4: Update runtime services labels**

In the runtime services card, replace `[deepgram, groq, teamNotifications]` with:

```ts
[stt, llm, teamNotifications]
```

Keep the runtime form fields for `deepgram_api_key`, `groq_api_key`, and `team_notification_email`; they still map to current backend runtime config. The visible readiness labels should now come from active `stt` and `llm` integrations instead of hard-coded provider keys.

- [ ] **Step 5: Run TypeScript and provider setup Playwright tests**

Run:

```powershell
cd apps\web
npx tsc --noEmit
npx playwright test tests/provider-setup.spec.ts --project=chromium --reporter=line
```

Expected: TypeScript passes and provider setup tests pass.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add apps/web/src/routes/_layout/settings.tsx apps/web/tests/provider-setup.spec.ts
git commit -m "fix: make provider setup the readiness source"
```

---

## Task 4: Verification And Status Note

**Files:**
- Modify: `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`

- [ ] **Step 1: Run targeted backend provider readiness tests**

Run:

```powershell
cd apps\api
uv run pytest tests/api/routes/test_utils.py tests/unit/test_setup_overview_provider_readiness.py tests/api/routes/test_provider_credentials.py tests/infrastructure/providers/test_registry.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run targeted frontend checks**

Run:

```powershell
cd apps\web
npx tsc --noEmit
npx playwright test tests/provider-setup.spec.ts --project=chromium --reporter=line
```

Expected: TypeScript and provider setup Playwright tests pass.

- [ ] **Step 3: Update the open review fix plan**

In `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`, under `### P1: Align Setup/Readiness UX With Provider Selection`, add this note immediately after the heading:

```markdown
Status update 2026-06-15: Backend setup overview was already capability-aware at the start of this slice. This pass completed the frontend Provider Setup alignment by rendering setup-overview integrations, worker readiness, and callback host status from `/api/v1/utils/setup-overview/`, while keeping provider selection on the catalog-backed `/settings/providers` route.
```

- [ ] **Step 4: Check diff and commit status note**

Run:

```powershell
git diff --check
git status --short
git add _bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md
git commit -m "docs: record provider readiness alignment"
```

Expected: no whitespace errors and only intended files are committed.

- [ ] **Step 5: Final status report**

Report:

```text
Provider readiness alignment complete.
Verified:
- Backend provider readiness tests: PASS
- Frontend TypeScript: PASS
- Provider setup Playwright: PASS

Remaining queue:
- P0 provider side-effect safety outside fixed workers
- P0 HTTP mutation idempotency
- P1 workspace authorization / BOLA hardening
- P1 Twilio callback replay dedupe
- docs/runbooks bootstrap
```

## Spec Coverage Review

- Active provider selections shown in setup/readiness UI: Tasks 1-2.
- Setup readiness no longer implies paid provider keys when local providers are selected: Tasks 1-3.
- Worker readiness reflects active providers: Tasks 1-2.
- Callback host status visible on provider setup route: Task 2.
- Stale fixed-provider settings page assumptions reduced: Task 3.
- Existing backend setup overview behavior preserved and tested: Task 4.

## Queue After This Plan

After this plan is implemented, run the next subagent plan for the first P0 hardening item in `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`: provider side-effect safety outside the fixed workers. Do not start that P0 until this provider readiness slice is committed and the targeted gates pass.
