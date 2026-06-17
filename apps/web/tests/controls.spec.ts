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
      }),
    })
  })
})

test("Controls focuses on pause and resume", async ({ page }) => {
  await page.route("**/api/v1/controls/pause", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })
  await page.route("**/api/v1/controls/resume", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })

  await page.goto("/controls")

  await expect(page.getByRole("heading", { name: "Outreach Controls" })).toBeVisible()
  await expect(page.getByText("Emergency pause")).toBeVisible()
  await expect(page.getByText("Daily sending limits")).toHaveCount(0)

  await page.getByLabel("Reason for pausing").fill("Compliance review")
  await page.getByRole("button", { name: "Pause all outreach" }).click()
  await expect(page.getByText("All outreach has been paused")).toBeVisible()
  await page.getByRole("button", { name: "Resume outreach" }).click()
  await expect(page.getByText("Outreach has been resumed")).toBeVisible()
})
