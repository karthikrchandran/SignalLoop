import { expect, type Route, test } from "@playwright/test"

const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
const ACME_ACCOUNT_ID = "22222222-2222-4222-8222-222222222222"

function accountRow(overrides: Record<string, unknown> = {}) {
  return {
    id: ACCOUNT_ID,
    workspace_id: "default",
    name: "Analytical Health",
    account_key: "analytical-health",
    website_url: null,
    industry: "Healthcare",
    status: "active",
    summary: "Analytical Health is evaluating cross-channel outreach.",
    tags: ["healthcare"],
    created_at: "2026-06-08T10:00:00Z",
    updated_at: "2026-06-08T10:00:00Z",
    contact_count: 2,
    last_activity_at: "2026-06-08T10:30:00Z",
    channel_counts: {
      chatbot: 1,
      email: 0,
      voice: 1,
      prospecting: 0,
    },
    top_next_action: "Reply with pricing clarity, then queue a call.",
    ...overrides,
  }
}

function accountsResponse(account: Record<string, unknown>) {
  return {
    data: [account],
    count: 1,
  }
}

function accountProfile() {
  return {
    account: {
      id: ACCOUNT_ID,
      workspace_id: "default",
      name: "Analytical Health",
      account_key: "analytical-health",
      website_url: null,
      industry: "Healthcare",
      status: "active",
      summary: "Multi-location healthcare buyer.",
      tags: ["pricing", "voice-ready"],
      created_at: "2026-06-08T10:00:00Z",
      updated_at: "2026-06-08T10:00:00Z",
    },
    contacts: [
      {
        id: "contact-ada",
        workspace_id: "default",
        account_id: ACCOUNT_ID,
        email: "ada@analytical.health",
        first_name: "Ada",
        last_name: "Lovelace",
        company: "Analytical Health",
        phone: "+1555010101",
        timezone: "America/New_York",
        created_at: "2026-06-08T10:10:00Z",
        display_name: "Ada Lovelace",
      },
      {
        id: "contact-grace",
        workspace_id: "default",
        account_id: ACCOUNT_ID,
        email: "grace@analytical.health",
        first_name: "Grace",
        last_name: "Hopper",
        company: "Analytical Health",
        phone: "+1555010102",
        timezone: "America/New_York",
        created_at: "2026-06-08T10:20:00Z",
        display_name: "Grace Hopper",
      },
    ],
    channel_summaries: {
      chatbot: {
        channel: "chatbot",
        label: "Chatbot",
        count: 1,
        status: "Active",
        detail: "Escalation captured from buyer chat.",
      },
      email: {
        channel: "email",
        label: "Email",
        count: 1,
        status: "Ready",
        detail: "Pricing follow-up drafted.",
      },
      voice: {
        channel: "voice",
        label: "Voice",
        count: 1,
        status: "Complete",
        detail: "Call completed with decision maker.",
      },
      prospecting: {
        channel: "prospecting",
        label: "Prospecting",
        count: 1,
        status: "Queued",
        detail: "Brief refreshed from account signals.",
      },
    },
    next_best_action: {
      title: "Reply with pricing clarity, then queue a call",
      reason: "The buyer asked for pricing and is ready for a voice follow-up.",
      source: "voice",
      priority: "high",
    },
    open_work: [
      {
        id: "work-chatbot-escalation",
        source: "chatbot",
        title: "Chatbot escalation",
        contact_id: "contact-ada",
        contact_name: "Ada Lovelace",
        status: "open",
        created_at: "2026-06-08T11:00:00Z",
      },
    ],
    prospecting_brief: {
      snapshot_id: "snapshot-analytical-health",
      contact_id: "contact-ada",
      account_summary:
        "Analytical Health is evaluating cross-channel outreach.",
      suggested_next_action: "Send pricing clarity and offer a voice call.",
      email_draft_available: true,
      voice_opener_available: true,
      created_at: "2026-06-08T11:30:00Z",
    },
    timeline: [
      {
        id: "timeline-voice-call",
        source: "voice",
        event_type: "call.completed",
        title: "Voice call completed",
        detail: "Pricing question needs a human",
        contact_id: "contact-ada",
        contact_name: "Ada Lovelace",
        timestamp: "2026-06-08T12:00:00Z",
      },
    ],
  }
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

test("shows Customer 360 accounts with channel rollups", async ({ page }) => {
  await page.route("**/api/v1/customer-360/accounts**", async (route) => {
    const url = new URL(route.request().url())

    if (
      url.pathname === `/api/v1/customer-360/accounts/${ACCOUNT_ID}` ||
      url.pathname.endsWith(`/customer-360/accounts/${ACCOUNT_ID}`)
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(accountProfile()),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(accountsResponse(accountRow())),
    })
  })

  await page.goto("/customer-360")

  await expect(
    page.getByRole("heading", { name: "Customer 360" }),
  ).toBeVisible()
  await expect(page.getByText("Analytical Health")).toBeVisible()
  await expect(page.getByText("2 contacts")).toBeVisible()
  await expect(page.getByText("Chatbot 1")).toBeVisible()
  await expect(page.getByText("Voice 1")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Open Analytical Health" }),
  ).toHaveAttribute("href", `/customer-360/${ACCOUNT_ID}`)

  await page.getByRole("link", { name: "Open Analytical Health" }).click()

  await expect(page).toHaveURL(new RegExp(`/customer-360/${ACCOUNT_ID}$`))
  await expect(
    page.getByRole("heading", { name: "Analytical Health" }),
  ).toBeVisible()
  await expect(page.getByText("Multi-location healthcare buyer.")).toBeVisible()
})

test("shows a Customer 360 account profile", async ({ page }) => {
  await page.route(
    `**/api/v1/customer-360/accounts/${ACCOUNT_ID}`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(accountProfile()),
      })
    },
  )

  await page.goto(`/customer-360/${ACCOUNT_ID}`)

  await expect(
    page.getByRole("heading", { name: "Analytical Health" }),
  ).toBeVisible()
  await expect(page.getByText("Multi-location healthcare buyer.")).toBeVisible()
  await expect(
    page.getByText("Ada Lovelace", { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByText("Grace Hopper", { exact: true })).toBeVisible()
  await expect(page.getByText("Chatbot", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Email", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Voice", { exact: true }).first()).toBeVisible()
  await expect(
    page.getByText("Prospecting", { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByText("Reply with pricing clarity, then queue a call"),
  ).toBeVisible()
  await expect(page.getByText("Unified account timeline")).toBeVisible()
  await expect(page.getByText("Voice call completed")).toBeVisible()
  await expect(page.getByText("Pricing question needs a human")).toBeVisible()
})

test("keeps searched accounts when the initial list response finishes later", async ({
  page,
}) => {
  let initialRoute: Route | undefined
  let searchedRoute: Route | undefined
  let resolveInitialRoute: (() => void) | undefined
  let resolveSearchedRoute: (() => void) | undefined
  const initialRouteReady = new Promise<void>((resolve) => {
    resolveInitialRoute = resolve
  })
  const searchedRouteReady = new Promise<void>((resolve) => {
    resolveSearchedRoute = resolve
  })

  await page.route("**/api/v1/customer-360/accounts**", (route) => {
    const url = new URL(route.request().url())
    expect(url.searchParams.get("limit")).toBe("50")

    if (url.searchParams.has("search")) {
      expect(url.searchParams.get("search")).toBe("Acme")
      searchedRoute = route
      resolveSearchedRoute?.()
      return
    }

    expect(url.searchParams.has("search")).toBe(false)
    initialRoute = route
    resolveInitialRoute?.()
  })

  await page.goto("/customer-360")
  await initialRouteReady

  await page.getByPlaceholder("Search accounts").fill("Acme  ")
  await page.getByPlaceholder("Search accounts").press("Enter")
  await searchedRouteReady

  if (!searchedRoute) throw new Error("Search request was not captured")
  await searchedRoute.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(
      accountsResponse(
        accountRow({
          id: ACME_ACCOUNT_ID,
          name: "Acme Ventures",
          account_key: "acme-ventures",
          industry: "Manufacturing",
          contact_count: 1,
          channel_counts: {
            chatbot: 0,
            email: 1,
            voice: 0,
            prospecting: 1,
          },
          top_next_action: "Send Acme the implementation follow-up.",
        }),
      ),
    ),
  })

  await expect(page.getByText("Acme Ventures")).toBeVisible()

  if (!initialRoute) throw new Error("Initial request was not captured")
  await initialRoute.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(accountsResponse(accountRow())),
  })
  await page.waitForTimeout(250)

  await expect(page.getByText("Acme Ventures")).toBeVisible()
  await expect(page.getByText("Analytical Health")).not.toBeVisible()
})
