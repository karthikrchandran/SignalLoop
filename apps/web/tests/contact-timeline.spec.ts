import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "ws-story-5-1")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "owner@example.com",
        full_name: "Timeline Owner",
        is_superuser: true,
      }),
    })
  })
})

test("contact timeline opens reason and transcript detail", async ({ page }) => {
  let detailRequested = false

  await page.route("**/api/v1/contacts/contact-1/timeline**", async (route) => {
    const url = new URL(route.request().url())
    const eventId = url.pathname.split("/timeline/")[1]

    if (eventId) {
      detailRequested = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: eventId,
          source_system: "call_sessions",
          event_type: "call_session",
          channel: "voice",
          timestamp: "2026-05-06T14:30:00Z",
          actor: "system",
          outcome: "completed",
          reason_code: "positive_email_signal",
          has_detail: true,
          reason_code_explanation: "The contact asked for a demo during follow-up.",
          transcript_excerpt: "Buyer said Tuesday morning works for the demo.",
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "call_11111111111111111111111111111111",
            source_system: "call_sessions",
            event_type: "call_session",
            channel: "voice",
            timestamp: "2026-05-06T14:30:00Z",
            actor: "system",
            outcome: "completed",
            reason_code: "positive_email_signal",
            has_detail: true,
          },
        ],
        count: 1,
        next_cursor: null,
      }),
    })
  })

  await page.goto("/contacts?contactId=contact-1&campaignId=campaign-1&contactName=Asha%20Rao")

  await expect(page.getByRole("heading", { name: "Asha Rao Timeline" })).toBeVisible()
  await expect(page.getByText("positive email signal")).toBeVisible()

  await page.getByText("call session").click()

  await expect(page.getByText("The contact asked for a demo during follow-up.")).toBeVisible()
  await expect(page.getByText("Transcript excerpt")).toBeVisible()
  await expect(page.getByText("Buyer said Tuesday morning works for the demo.")).toBeVisible()
  expect(detailRequested).toBe(true)
})