import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "admin@example.com",
        full_name: "Revenue Admin",
        is_superuser: true,
        role: "admin",
      }),
    })
  })
})

test("Revenue OS shows the connected agent workforce and specialist workspaces", async ({ page }) => {
  await page.goto("/revenue-os")

  await expect(page.getByRole("heading", { name: "Revenue OS" })).toBeVisible()
  await expect(page.getByText("One customer record. One operating rhythm.")).toBeVisible()
  await expect(page.getByText("Capture", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Qualify & Pipeline", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Fulfill & Get Paid", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Incentives & Performance", { exact: true }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Open EngageHub" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Sales Ops" })).toBeVisible()
})
