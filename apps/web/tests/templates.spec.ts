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
        full_name: "Template Owner",
        is_superuser: true,
      }),
    })
  })
})

test("Template preview shows unresolved token warning", async ({ page }) => {
  await page.route("**/api/v1/templates/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [
            {
              id: "tpl-1",
              name: "Welcome",
              channel: "email",
              current_version: {
                id: "tv-1",
                version_number: 1,
                status: "draft",
                guardrail_compliant: false,
                subject: "Hi {{contact.firstName}}",
                content: "Hello {{contact.firstName}} {{contact.lastName}}",
              },
            },
          ],
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "tpl-new" }),
    })
  })

  await page.route("**/api/v1/templates/tpl-1/preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        rendered_content: "Hello Asha {{contact.lastName}}",
        unresolved_tokens: ["contact.lastName"],
      }),
    })
  })

  await page.goto("/templates")

  await page.getByRole("button", { name: "Preview tokens" }).click()

  await expect(page.getByText("Rendered preview")).toBeVisible()
  await expect(page.getByText("Hello Asha {{contact.lastName}}"))
    .toBeVisible()
  await expect(page.getByText("Unresolved tokens: contact.lastName")).toBeVisible()
})
