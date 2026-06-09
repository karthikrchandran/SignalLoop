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
