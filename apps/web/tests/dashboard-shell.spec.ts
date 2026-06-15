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

test("renders the Liquid Steel shell and dashboard layout", async ({ page }) => {
  await page.goto("/")

  await expect(page.locator("html")).toHaveClass(/light/)
  await expect(
    page.getByRole("heading", { name: "Campaign control at a glance" }),
  ).toBeVisible()
  await expect(page.getByText("Priority queue")).toBeVisible()
  await expect(page.getByText("System health")).toBeVisible()
  await expect(page.getByText("Dashboard", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Quick access")).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Quick access" }),
  ).not.toBeVisible()
})
