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
  await expect(page.getByRole("link", { name: "Products" })).toHaveAttribute("href", "/platform/products")
  await expect(page.getByRole("link", { name: "Identity" })).toHaveAttribute("href", "/platform/identity")
  await expect(page.getByRole("link", { name: "Messaging defaults" })).toHaveAttribute("href", "/platform/messaging")
  await expect(page.getByRole("link", { name: "Provider policies" })).toHaveAttribute("href", "/platform/provider-policies")
  await expect(page.getByRole("link", { name: "Usage and health" })).toHaveAttribute("href", "/platform/usage-health")
  await expect(page.getByRole("link", { name: "Support access" })).toHaveAttribute("href", "/platform/support-access")
  await expect(page.getByRole("link", { name: "Audit" })).toHaveAttribute("href", "/platform/audit")
})
