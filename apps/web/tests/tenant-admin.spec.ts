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
  await expect(page.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/admin")
  await expect(
    page.getByRole("link", { name: "People and roles" }),
  ).toHaveAttribute("href", "/admin/members")
  await expect(page.getByRole("link", { name: "Products" })).toHaveAttribute("href", "/admin/products")
  await expect(page.getByRole("link", { name: "Branding" })).toHaveAttribute("href", "/admin/branding")
  await expect(page.getByRole("link", { name: "Security" })).toHaveAttribute("href", "/admin/security")
  await expect(page.getByRole("link", { name: "Messaging" })).toHaveAttribute("href", "/admin/messaging")
  await expect(page.getByRole("link", { name: "Tenant audit" })).toHaveAttribute("href", "/admin/audit")
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

for (const product of [
  { capability: "commitarc.admin.manage", path: "/admin/commit-arc", title: "CommitArc administration" },
  { capability: "revenueos.admin.manage", path: "/admin/revenue-os", title: "RevenueOS administration" },
  { capability: "signalloop.admin.manage", path: "/admin/signal-loop", title: "SignalLoop administration" },
]) {
  test(`${product.title} requires its product administration capability`, async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("access_token", "e2e-test-token")
      localStorage.setItem("workspace_id", "ara")
    })
    await page.route("**/api/v1/users/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "ara-product-admin",
          email: "product-admin@ara.example",
          full_name: "ARA Product Admin",
          is_superuser: false,
          role: "admin",
        }),
      })
    })
    await page.route("**/api/v1/me/suite-context", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          tenant: { key: "ara", display_name: "ARA" },
          roles: ["PRODUCT_ADMIN"],
          capabilities: ["tenant.members.manage"],
          products: {
            commitarc: { visible: true, capabilities: [] },
            revenueos: { visible: true, capabilities: [] },
            signalloop: { visible: true, capabilities: [] },
          },
          default_route: "/",
        }),
      })
    })

    await page.goto(product.path)

    await expect(page).toHaveURL(/\/$/)
  })
}
