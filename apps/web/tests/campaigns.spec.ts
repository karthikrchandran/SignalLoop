import { expect, test } from "@playwright/test"

const campaignsPayload = {
  data: [
    {
      id: "camp-draft-1",
      name: "Q2 Product Outreach",
      status: "draft",
      created_at: "2026-06-20T14:30:00Z",
    },
    {
      id: "camp-live-1",
      name: "Launch Wave",
      status: "active",
      created_at: "2026-06-19T10:15:00Z",
    },
    {
      id: "camp-paused-1",
      name: "Win-back Follow-up",
      status: "paused",
      created_at: "2026-06-18T09:00:00Z",
    },
  ],
  count: 3,
}

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "owner@example.com",
        full_name: "Campaign Owner",
        is_superuser: true,
      }),
    })
  })

  await page.route("**/api/v1/campaigns/", async (route) => {
    const method = route.request().method()

    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(campaignsPayload),
      })
      return
    }

    if (method === "PUT") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "ok" }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "camp-created-1",
        name: "New draft",
        status: "draft",
        created_at: "2026-06-23T12:00:00Z",
      }),
    })
  })
})

test("campaign lifecycle hub links into the route slices", async ({ page }) => {
  await page.goto("/campaigns")

  await expect(page.getByRole("heading", { level: 1, name: "Campaign lifecycle" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Draft" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Running" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Paused" })).toBeVisible()
})

test("draft campaigns page keeps the builder secondary to the list", async ({ page }) => {
  await page.goto("/campaigns/draft")

  await expect(page.getByRole("heading", { level: 1, name: "Draft campaigns" })).toBeVisible()
  await expect(page.getByRole("heading", { level: 1, name: "Campaign draft builder" })).toBeVisible()
  await expect(page.getByText("Q2 Product Outreach")).toBeVisible()
})

test("running campaigns page exposes pause actions", async ({ page }) => {
  await page.goto("/campaigns/running")

  await expect(page.getByRole("heading", { level: 1, name: "Running campaigns" })).toBeVisible()
  await Promise.all([
    page.waitForRequest((request) =>
      request.url().includes("/api/v1/campaigns/camp-live-1/pause"),
    ),
    page.getByRole("button", { name: "Pause" }).click(),
  ])
})

test("paused campaigns page exposes resume actions", async ({ page }) => {
  await page.goto("/campaigns/paused")

  await expect(page.getByRole("heading", { level: 1, name: "Paused campaigns" })).toBeVisible()
  await Promise.all([
    page.waitForRequest((request) =>
      request.url().includes("/api/v1/campaigns/camp-paused-1/resume"),
    ),
    page.getByRole("button", { name: "Resume" }).click(),
  ])
})
