import { expect, test } from "@playwright/test"

const contactsPayload = {
  data: [
    {
      id: "contact-1",
      email: "ada@example.com",
      first_name: "Ada",
      last_name: "Lovelace",
      company: "Analytical",
      phone: "+15551234567",
      timezone: "America/New_York",
      industry: "Financial Services",
      title: "VP Operations",
      product_interest: "Voice AI",
      source: "Messaging Hub",
      created_at: "2026-06-08T10:00:00Z",
    },
    {
      id: "contact-2",
      email: "grace@example.com",
      first_name: "Grace",
      last_name: "Hopper",
      company: "Compiler Co",
      phone: null,
      timezone: "UTC",
      industry: "Software",
      title: "CTO",
      product_interest: "Email Automation",
      source: "CSV Import",
      created_at: "2026-06-08T10:00:00Z",
    },
  ],
  count: 2,
}

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
        email: "owner@example.com",
        full_name: "Contacts Owner",
        is_superuser: true,
      }),
    })
  })

  await page.route("**/api/v1/contacts/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(contactsPayload),
    })
  })
})

test("Contacts page separates contacts, lead groups, and import", async ({ page }) => {
  await page.goto("/contacts")

  await expect(page.getByRole("heading", { name: "Contacts" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Contacts" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Lead Groups" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Import" })).toBeVisible()
  await expect(page.getByText("ada@example.com")).toBeVisible()
  await expect(page.getByLabel("Industry")).toBeVisible()
  await expect(page.getByLabel("Product interest")).toBeVisible()
  await expect(page.getByRole("navigation", { name: "pagination" })).toBeVisible()

  await page.getByLabel("Industry").selectOption("Software")
  await expect(page.getByText("grace@example.com")).toBeVisible()
  await expect(page.getByText("ada@example.com")).toHaveCount(0)

  await page.getByRole("tab", { name: "Import" }).click()
  await expect(page.getByText("CSV file")).toBeVisible()
  await expect(page.getByRole("button", { name: "Analyze" })).toBeVisible()
})

test("Lead Groups opens a detail screen with matching leads", async ({ page }) => {
  await page.goto("/contacts")
  await page.getByRole("tab", { name: "Lead Groups" }).click()

  await expect(page.getByRole("heading", { name: "Lead Groups" })).toBeVisible()
  await page.getByRole("link", { name: /Financial Services leaders/i }).click()

  await expect(page).toHaveURL(/leadGroupId=financial-services-leaders/)
  await expect(page.getByRole("heading", { name: "Financial Services leaders" })).toBeVisible()
  await expect(page.getByText("ada@example.com")).toBeVisible()
  await expect(page.getByText("Industry contains Financial Services")).toBeVisible()
})
