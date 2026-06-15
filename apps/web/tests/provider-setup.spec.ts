import { expect, type Page, test } from "@playwright/test"

const providerOptions = {
  data: [
    {
      capability: "email",
      providers: [
        {
          provider: "sendgrid",
          label: "SendGrid",
          requires_creds: true,
          free_tier: "100 emails/day",
          local: false,
        },
        {
          provider: "smtp",
          label: "Generic SMTP / Mailpit",
          requires_creds: false,
          free_tier: "Free local inbox",
          local: true,
        },
      ],
    },
    {
      capability: "llm",
      providers: [
        {
          provider: "groq",
          label: "Groq",
          requires_creds: true,
          free_tier: "Free tier",
          local: false,
        },
        {
          provider: "ollama_local",
          label: "Ollama",
          requires_creds: false,
          free_tier: "Free local hardware",
          local: true,
        },
      ],
    },
    {
      capability: "voice",
      providers: [
        {
          provider: "twilio",
          label: "Twilio Voice",
          requires_creds: true,
          free_tier: "$15 trial credit",
          local: false,
        },
        {
          provider: "vapi",
          label: "Vapi AI Voice",
          requires_creds: true,
          free_tier: "Starter credits / free testing numbers",
          local: false,
        },
      ],
    },
    {
      capability: "stt",
      providers: [
        {
          provider: "deepgram",
          label: "Deepgram Nova-2",
          requires_creds: true,
          free_tier: "$200 credit",
          local: false,
        },
        {
          provider: "faster_whisper_local",
          label: "Faster Whisper Local",
          requires_creds: false,
          free_tier: "Free local hardware",
          local: true,
        },
      ],
    },
  ],
}

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
      config: {
        host: "localhost",
        port: "1025",
        from_email: "demo@example.com",
      },
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

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "default")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "admin@example.com",
        full_name: "Admin User",
        is_superuser: true,
      }),
    })
  })
})

type ProviderSelectionRequest = {
  capability: string
  provider: string
}

async function mockProviderEndpoints(
  page: Page,
  putRequests: ProviderSelectionRequest[] = [],
  overviewRequests: string[] = [],
  overviewResponse: unknown = setupOverview,
  overviewStatus = 200,
) {
  const selections = new Map([
    ["email", "smtp"],
    ["llm", "groq"],
    ["voice", "vapi"],
    ["stt", "faster_whisper_local"],
  ])

  await page.route(
    "**/api/v1/workspaces/default/provider-options",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(providerOptions),
      })
    },
  )

  await page.route(
    "**/api/v1/workspaces/default/provider-selection",
    async (route) => {
      if (route.request().method() === "PUT") {
        const body = route.request().postDataJSON() as ProviderSelectionRequest
        putRequests.push(body)
        selections.set(body.capability, body.provider)
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: `selection-${body.capability}`,
            workspace_id: "default",
            capability: body.capability,
            provider: body.provider,
            is_active: true,
          }),
        })
        return
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [...selections.entries()].map(([capability, provider]) => ({
            id: `selection-${capability}`,
            workspace_id: "default",
            capability,
            provider,
            is_active: true,
          })),
          count: selections.size,
        }),
      })
    },
  )

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    overviewRequests.push(route.request().url())
    await route.fulfill({
      status: overviewStatus,
      contentType: "application/json",
      body: JSON.stringify(overviewResponse),
    })
  })
}

test("renders provider sections for catalog capabilities including Vapi voice", async ({
  page,
}) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(
    page.getByRole("heading", { name: "Provider Setup" }),
  ).toBeVisible()
  await expect(page.getByTestId("provider-card-email")).toContainText("Email")
  await expect(page.getByTestId("provider-card-voice")).toContainText("Voice")
  await expect(page.getByTestId("provider-card-voice")).toContainText(
    "Vapi AI Voice",
  )
  await expect(page.getByTestId("provider-card-llm")).toContainText("LLM")
  await expect(page.getByTestId("provider-card-stt")).toContainText("STT")
})

test("selecting a provider calls the PUT endpoint", async ({ page }) => {
  const putRequests: ProviderSelectionRequest[] = []
  const overviewRequests: string[] = []
  await mockProviderEndpoints(page, putRequests, overviewRequests)

  await page.goto("/settings/providers")
  await expect.poll(() => overviewRequests.length).toBeGreaterThanOrEqual(1)
  const initialOverviewRequests = overviewRequests.length
  await page.getByLabel("Provider for LLM").click()
  await page.getByRole("option", { name: "Ollama" }).click()

  await expect
    .poll(() => putRequests)
    .toEqual([{ capability: "llm", provider: "ollama_local" }])
  await expect
    .poll(() => overviewRequests.length)
    .toBeGreaterThan(initialOverviewRequests)
})

test("shows local badge for local selected providers", async ({ page }) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(
    page.getByTestId("provider-card-stt").getByText("Local", { exact: true }),
  ).toBeVisible()
})

test("renders setup overview readiness from capability-aware endpoint", async ({
  page,
}) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(page.getByTestId("provider-card-email")).toContainText("Ready")
  await expect(page.getByTestId("provider-card-email")).toContainText(
    "localhost",
  )
  await expect(page.getByTestId("provider-card-voice")).toContainText(
    "Missing setup",
  )
  await expect(page.getByTestId("provider-worker-readiness")).toContainText(
    "Call worker",
  )
  await expect(page.getByTestId("provider-worker-readiness")).toContainText(
    "voice provider",
  )
  await expect(page.getByTestId("provider-callback-status")).toContainText(
    "Local only",
  )
})

test("shows setup overview errors instead of hiding readiness state", async ({
  page,
}) => {
  await mockProviderEndpoints(
    page,
    [],
    [],
    { detail: "Provider readiness unavailable" },
    500,
  )

  await page.goto("/settings/providers")

  await expect(page.getByText("Provider readiness unavailable")).toBeVisible()
})

test("settings workspace setup hands off provider readiness to Provider Setup", async ({
  page,
}) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings")
  await page.getByRole("tab", { name: "Workspace setup" }).click()

  await expect(page.getByText("Provider readiness")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Open Provider Setup" }),
  ).toHaveAttribute("href", "/settings/providers")
  await expect(page.getByText("EMAIL: Generic SMTP / Mailpit")).toBeVisible()
})
