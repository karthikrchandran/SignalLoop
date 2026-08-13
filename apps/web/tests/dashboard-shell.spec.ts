import { expect, test } from "@playwright/test"

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
        role: "admin",
      }),
    })
  })
})

test("renders the Revenue OS launcher in the application shell", async ({
  page,
}) => {
  await page.goto("/")
  await expect(page.locator("html")).toHaveClass(/light/)
  await expect(page.getByRole("heading", { name: "Revenue OS" })).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Your workspaces" }),
  ).toBeVisible()
  await expect(
    page.getByText("One customer record. One operating rhythm."),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: /EngageHub/ })).toBeVisible()
  await expect(
    page.getByRole("link", { name: /Platform administration/ }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Agent workforce" }),
  ).toBeVisible()
})

test("Revenue OS workspace links navigate to internal workspaces", async ({
  page,
}) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [{ id: "camp-1", name: "Q2 Outreach", status: "draft" }],
        count: 1,
      }),
    })
  })
  await page.goto("/")
  await page.getByRole("link", { name: /Open EngageHub/ }).click()
  await expect(page).toHaveURL(/\/campaigns/)
  await expect(
    page.getByRole("heading", { name: "Campaign lifecycle" }),
  ).toBeVisible()
  await page.goto("/")
  await page.getByRole("link", { name: /Open administration/ }).click()
  await expect(page).toHaveURL(/\/admin/)
})
