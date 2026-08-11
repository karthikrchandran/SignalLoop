import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test("tenant administrator sees tenant-scoped navigation", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "tenant-admin",
        email: "owner@ara.example",
        full_name: "ARA Owner",
        is_superuser: true,
        role: "admin",
      }),
    })
  })

  await page.goto("/admin")

  await expect(page.getByRole("heading", { name: "Tenant administration" })).toBeVisible()
  await expect(page.getByRole("link", { name: "People and roles" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Products" })).toBeVisible()
})
