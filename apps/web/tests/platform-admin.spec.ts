import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test("platform administrator sees control-plane navigation", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "platform-admin",
        email: "platform@example.com",
        full_name: "Platform Admin",
        is_superuser: true,
        role: "platform_admin",
      }),
    })
  })

  await page.goto("/platform")

  await expect(page.getByRole("heading", { name: "Platform administration" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Tenants" })).toHaveAttribute(
    "href",
    "/platform/tenants",
  )
  await expect(page.getByRole("link", { name: "Support access" })).toBeVisible()
})
