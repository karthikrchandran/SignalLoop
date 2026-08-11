import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "ara-global")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "employee@example.com",
        full_name: "Employee",
        is_superuser: false,
      }),
    })
  })
})

test("employee sees CommitArc and RevenueOS Essentials but no SignalLoop authoring", async ({
  page,
}) => {
  await page.route("**/api/v1/me/suite-context", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tenant: { key: "ara-global", display_name: "ARA Global" },
        roles: ["EMPLOYEE"],
        capabilities: ["revenueos.essentials.read"],
        products: {
          commitarc: { visible: true, mode: "FULL", href: "/commitarc", capabilities: [] },
          revenueos: { visible: true, mode: "ESSENTIALS", href: "/", capabilities: ["revenueos.essentials.read"] },
          signalloop: { visible: false, mode: null, href: null, capabilities: [] },
        },
        default_route: "/",
      }),
    })
  })
  await page.route("**/api/v1/revenueos/essentials", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        generated_at: "2026-08-10T00:00:00Z",
        source_freshness: [
          {
            source: "CommitArc",
            status: "UNAVAILABLE",
            message: "No signed CommitArc projection has been received for this tenant.",
            observed_at: null,
          },
        ],
        cards: [],
        metrics: [],
        blocked_actions: ["Connect a signed CommitArc projection before recommendations can be generated."],
        permitted_questions: [],
        personal_goals: [],
        intervention_outcomes: [],
      }),
    })
  })

  await page.goto("/home")

  await expect(
    page.getByRole("link", { name: "CommitArc", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: "RevenueOS Essentials", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText("No signed CommitArc projection has been received for this tenant."),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: /Open campaigns/i })).toHaveCount(0)
})
