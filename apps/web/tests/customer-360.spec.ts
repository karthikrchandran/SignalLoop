import { expect, test } from "@playwright/test"

const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"

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

  await page.route("**/api/v1/customer-360/accounts**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
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
          },
        ],
        count: 1,
      }),
    })
  })
})

test("shows Customer 360 accounts with channel rollups", async ({ page }) => {
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
