import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "owner@example.com",
        full_name: "Campaign Owner",
        is_superuser: true,
      }),
    })
  })
})

test("Campaign wizard shows mapping preview (20 rows) and invalid-row reasons", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "camp-1", name: "Q2 Outreach", status: "draft" }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-1/contacts/import", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        import_id: "imp-1",
        headers: ["email", "firstName", "company", "timezone"],
        valid_rows: 20,
        invalid_rows: 1,
        errors: [
          {
            row_number: 3,
            column: "email",
            message: "Email is required",
          },
        ],
      }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-1/contacts/mapping", async (route) => {
    const previewRows = Array.from({ length: 20 }, (_, index) => ({
      row_number: index + 1,
      data: {
        email: `user${index + 1}@example.com`,
        firstName: `Name${index + 1}`,
      },
    }))
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        import_id: "imp-1",
        preview_rows: previewRows,
        errors: [],
      }),
    })
  })

  await page.goto("/campaigns")

  await page.getByLabel("Campaign name").fill("Q2 Outreach")
  await page.getByRole("button", { name: "Continue" }).click()

  await page
    .locator('input[type="file"]')
    .setInputFiles({
      name: "contacts.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("email,firstName,company,timezone\nuser@example.com,Jane,Acme,UTC\n"),
    })
  await page.getByRole("button", { name: "Continue" }).click()

  await expect(page.getByText("Validation issues")).toBeVisible()
  await expect(page.getByText("Row 3, email: Email is required")).toBeVisible()

  await page.getByRole("button", { name: "Continue" }).click()

  await expect(page.getByText("Preview rows")).toBeVisible()
  await expect(page.getByText("user20@example.com")).toBeVisible()

  await page.getByRole("button", { name: "Continue" }).click()
  await expect(page.getByText("Current step:").locator("..")).toContainText("4. Segmentation")
})

test("Campaign wizard can complete draft flow end-to-end", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "camp-2", name: "Launch Wave", status: "draft" }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-2/contacts/import", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        import_id: "imp-2",
        headers: ["email", "firstName", "company", "timezone"],
        valid_rows: 2,
        invalid_rows: 0,
        errors: [],
      }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-2/contacts/mapping", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        import_id: "imp-2",
        preview_rows: [
          { row_number: 1, data: { email: "a@example.com", firstName: "A" } },
          { row_number: 2, data: { email: "b@example.com", firstName: "B" } },
        ],
        errors: [],
      }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-2/segments", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })

  await page.route("**/api/v1/offer-packs/assignable", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "op-1",
            name: "Starter Pack",
            current_version: {
              id: "opv-1",
              version_number: 1,
              status: "published",
              is_default: true,
              guardrail_compliant: true,
            },
          },
        ],
        count: 1,
      }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-2/strategy", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })

  await page.goto("/campaigns")

  await page.getByLabel("Campaign name").fill("Launch Wave")
  await page.getByRole("button", { name: "Continue" }).click()

  await page
    .locator('input[type="file"]')
    .setInputFiles({
      name: "contacts.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("email,firstName,company,timezone\na@example.com,A,Acme,UTC\n"),
    })
  await page.getByRole("button", { name: "Continue" }).click()

  await page.getByRole("button", { name: "Continue" }).click()
  await page.getByRole("button", { name: "Continue" }).click()

  await page.getByLabel("Value").fill("Technology")
  await page.getByRole("button", { name: "Continue" }).click()

  await page.getByRole("button", { name: "Save strategy" }).click()
  await expect(page.getByRole("alert")).toContainText("Campaign intake flow complete. Draft strategy saved.")
})
