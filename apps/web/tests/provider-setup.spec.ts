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
) {
  const selections = new Map([
    ["email", "smtp"],
    ["llm", "groq"],
    ["stt", "faster_whisper_local"],
  ])

  await page.route("**/api/v1/workspaces/default/provider-options", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(providerOptions),
    })
  })

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
}

test("renders one provider section per local-demo capability", async ({ page }) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(page.getByRole("heading", { name: "Provider Setup" })).toBeVisible()
  await expect(page.getByTestId("provider-card-email")).toContainText("Email")
  await expect(page.getByTestId("provider-card-llm")).toContainText("LLM")
  await expect(page.getByTestId("provider-card-stt")).toContainText("STT")
})

test("selecting a provider calls the PUT endpoint", async ({ page }) => {
  const putRequests: ProviderSelectionRequest[] = []
  await mockProviderEndpoints(page, putRequests)

  await page.goto("/settings/providers")
  await page.getByLabel("Provider for LLM").click()
  await page.getByRole("option", { name: "Ollama" }).click()

  await expect.poll(() => putRequests).toEqual([
    { capability: "llm", provider: "ollama_local" },
  ])
})

test("shows local badge for local selected providers", async ({ page }) => {
  await mockProviderEndpoints(page)

  await page.goto("/settings/providers")

  await expect(
    page.getByTestId("provider-card-stt").getByText("Local", { exact: true }),
  ).toBeVisible()
})
