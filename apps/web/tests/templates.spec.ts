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

test("Template library can filter and page reusable content", async ({ page }) => {
  await page.route("**/api/v1/templates/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "tpl-1",
            name: "Email Welcome",
            channel: "email",
            current_version: {
              id: "tv-1",
              version_number: 1,
              status: "draft",
              guardrail_compliant: false,
              subject: "Hi {{contact.firstName}}",
              content: "Hello {{contact.firstName}}",
            },
          },
          {
            id: "tpl-2",
            name: "Voice Opener",
            channel: "voice",
            current_version: {
              id: "tv-2",
              version_number: 1,
              status: "published",
              guardrail_compliant: true,
              subject: null,
              content: "Hi, this is a quick follow-up.",
            },
          },
        ],
      }),
    })
  })

  await page.goto("/templates")

  await expect(page.getByLabel("Search templates")).toBeVisible()
  await page.getByLabel("Channel", { exact: true }).selectOption("voice")
  await expect(page.getByRole("button", { name: /Voice Opener voice \/ published/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /Email Welcome email \/ draft/ })).toHaveCount(0)
  await expect(page.getByRole("navigation", { name: "pagination" })).toBeVisible()
})
