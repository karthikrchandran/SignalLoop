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
  await expect(
    page.getByRole("link", { name: "People and roles" }),
  ).toHaveAttribute("href", "/admin/members")
  await expect(page.getByRole("link", { name: "Products" })).toBeVisible()
})

test("tenant member manager can open their tenant's people page", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "ara")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "ara-owner",
        email: "owner@ara.example",
        full_name: "ARA Owner",
        is_superuser: false,
        role: "owner",
      }),
    })
  })
  await page.route("**/api/v1/me/suite-context", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tenant: { key: "ara", display_name: "ARA" },
        roles: ["TENANT_OWNER"],
        capabilities: ["tenant.members.manage"],
        products: {
          commitarc: { visible: false, capabilities: [] },
          revenueos: { visible: false, capabilities: [] },
          signalloop: { visible: true, capabilities: [] },
        },
        default_route: "/",
      }),
    })
  })

  await page.goto("/admin/members")

  await expect(page.getByRole("heading", { name: "People and roles" })).toBeVisible()
})

test("tenant user without an administration capability is redirected", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "ara")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "ara-user",
        email: "user@ara.example",
        full_name: "ARA User",
        is_superuser: false,
        role: "member",
      }),
    })
  })
  await page.route("**/api/v1/me/suite-context", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tenant: { key: "ara", display_name: "ARA" },
        roles: ["TENANT_MEMBER"],
        capabilities: [],
        products: {
          commitarc: { visible: false, capabilities: [] },
          revenueos: { visible: false, capabilities: [] },
          signalloop: { visible: true, capabilities: [] },
        },
        default_route: "/",
      }),
    })
  })

  await page.goto("/admin/members")

  await expect(page).toHaveURL(/\/$/)
})
