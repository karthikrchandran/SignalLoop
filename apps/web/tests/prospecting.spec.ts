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

test("runs prospecting research and shows outreach drafts", async ({ page }) => {
  await page.route(/\/api\/v1\/contacts\/?(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "11111111-1111-4111-8111-111111111111",
            workspace_id: "default",
            email: "ada@example.com",
            first_name: "Ada",
            last_name: "Lovelace",
            company: "Analytical",
            phone: "+15551234567",
            timezone: "America/New_York",
            created_at: "2026-06-08T10:00:00Z",
          },
          {
            id: "22222222-2222-4222-8222-222222222222",
            workspace_id: "default",
            email: "grace@example.com",
            first_name: "Grace",
            last_name: "Hopper",
            company: "Compiler Co",
            phone: null,
            timezone: "UTC",
            created_at: "2026-06-08T10:00:00Z",
          },
        ],
        count: 2,
      }),
    })
  })

  await page.route("**/api/v1/prospecting/research", async (route) => {
    expect(route.request().method()).toBe("POST")
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "33333333-3333-4333-8333-333333333333",
        contact_id: "11111111-1111-4111-8111-111111111111",
        company_url: "https://analytical.example",
        account_summary: "Ada Lovelace is a prospect at Analytical with pricing and follow-up intent.",
        pain_points: [
          "Improve outbound conversion from existing CRM signals.",
          "Coordinate email and voice follow-up.",
        ],
        objections: ["May already use a CRM or enrichment workflow."],
        personalization_bullets: [
          "Reference Analytical directly.",
          "Mention pricing and follow-up intent.",
        ],
        suggested_next_action: "Send the email draft, then call with the voice opener.",
        email_draft: "Subject: Idea for Analytical outreach follow-up\n\nHi Ada,",
        voice_opener: "Hi Ada, this is EngageHub calling about Analytical.",
        sources: [{ label: "CRM contact", summary: "Ada at Analytical" }],
        created_at: "2026-06-08T10:01:00Z",
      }),
    })
  })

  await page.goto("/prospecting")

  await expect(page.getByRole("heading", { name: "Prospecting" })).toBeVisible()
  await page.getByLabel("Contact", { exact: true }).selectOption("11111111-1111-4111-8111-111111111111")
  await page.getByLabel("Company website").fill("https://analytical.example")
  await page.getByRole("button", { name: "Run research" }).click()

  await expect(page.getByText("Ada Lovelace is a prospect at Analytical")).toBeVisible()
  await expect(page.getByText("Subject: Idea for Analytical outreach follow-up")).toBeVisible()
  await expect(page.getByText("Hi Ada, this is EngageHub calling about Analytical.")).toBeVisible()
})
