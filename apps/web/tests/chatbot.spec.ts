import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("chatbot_demo_mode", "true")
    window.localStorage.setItem("access_token", "demo-token")
    window.localStorage.setItem("workspace_id", "demo-workspace")
  })
})

test("Chatbot setup and knowledge mockups render with test bot flow", async ({ page }) => {
  await page.goto("/chatbot")
  await expect(page).toHaveURL(/\/chatbot\/channels/)

  await page.goto("/chatbot/channels")

  await expect(page.getByRole("heading", { name: "Channels" })).toBeVisible()
  await expect(page.getByText("Facebook Messenger")).toBeVisible()
  await expect(page.getByText("WhatsApp Business")).toBeVisible()
  await expect(page.getByText("Telegram", { exact: true })).toBeVisible()
  await expect(page.getByText("Real-connect readiness")).toBeVisible()
  await expect(page.getByText("2 of 3 channels ready")).toBeVisible()
  await expect(page.getByText("Ready for live traffic").first()).toBeVisible()
  await expect(page.getByText("Needs activation and webhook verification")).toBeVisible()
  await expect(page.getByText("/api/v1/chatbot/webhooks/demo-channel-wa")).toBeVisible()

  await page.getByRole("button", { name: "Edit" }).first().click()
  await expect(page.getByText("Facebook Messenger connection")).toBeVisible()
  await page.keyboard.press("Escape")

  await page.goto("/chatbot/knowledge-base")
  await expect(page.getByRole("heading", { name: "Knowledge Base" })).toBeVisible()
  await expect(page.getByText("Pricing and demo FAQ")).toBeVisible()

  await page.getByRole("button", { name: "Test Bot" }).click()
  await page.getByPlaceholder("Ask a question").fill("How does pricing work?")
  await page.getByRole("button", { name: "Send" }).click()
  await expect(page.getByText("pricing depends on usage")).toBeVisible()
  await expect(page.getByText("Demo source excerpt")).toBeVisible()
})

test("Chatbot inbox detail and analytics mockups render", async ({ page }) => {
  await page.goto("/chatbot/inbox/demo-thread-escalated")

  await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible()
  await expect(page.getByText("Maya Singh")).toBeVisible()
  await expect(page.getByText("Can someone help me compare pricing for three locations?")).toBeVisible()
  await expect(page).toHaveURL(/\/chatbot\/inbox\/demo-thread-escalated/)

  await page.goto("/chatbot/analytics")
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible()
  await expect(page.getByText("Conversations").first()).toBeVisible()
  await expect(page.getByText("Containment")).toBeVisible()
  await expect(page.getByText("Conversion funnel")).toBeVisible()
  await expect(page.getByText("Prospecting researched")).toBeVisible()
  await expect(page.getByText("Voice follow-up")).toBeVisible()
  await expect(page.getByText("Outcome breakdown")).toBeVisible()
  await expect(page.getByText("WhatsApp Business")).toBeVisible()
})

test("Chatbot opt-outs and dead-letter recovery mockups render actions", async ({ page }) => {
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Opt-outs" }).click()
  await expect(page.getByText("15559876543")).toBeVisible()
  await page.getByRole("button", { name: "Re-enable" }).click()
  await expect(page.getByText("requires explicit visitor re-consent")).toBeVisible()
  await page.getByRole("button", { name: "Cancel" }).click()

  await page.goto("/admin/chatbot/dead-letters")
  await expect(page.getByRole("heading", { name: "Messaging Dead Letters" })).toBeVisible()
  await expect(page.getByText("wamid.demo.failed")).toBeVisible()
  await page.getByRole("button", { name: "Retry" }).first().click()
  await expect(page.getByText("Dead-lettered message requeued")).toBeVisible()
})

test("Messaging Hub analytics shows no-data state for empty API results", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.removeItem("chatbot_demo_mode")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "user-1", email: "admin@example.com", is_superuser: true, role: "admin" }),
    })
  })
  await page.route("**/api/v1/chatbot/analytics**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "default",
        date_from: "2026-06-10",
        date_to: "2026-06-16",
        updated_at: "2026-06-16T12:00:00Z",
        totals: { conversations: 0, containment_rate: 0, leads_captured: 0, escalations: 0, bot_messages: 0, opt_outs: 0 },
        conversion_funnel: { conversations: 0, leads_captured: 0, prospecting_researched: 0, added_to_campaign: 0, sequence_enrolled: 0, voice_followups: 0 },
        timeseries: [],
        channel_breakdown: [],
      }),
    })
  })

  await page.goto("/chatbot/analytics")

  await expect(page.getByText("No messaging analytics for this range").first()).toBeVisible()
  await expect(page.getByText("No data for this range").first()).toBeVisible()
})

test("Messaging Hub analytics shows retryable error state", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.removeItem("chatbot_demo_mode")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "user-1", email: "admin@example.com", is_superuser: true, role: "admin" }),
    })
  })
  await page.route("**/api/v1/chatbot/analytics**", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "analytics unavailable" }),
    })
  })

  await page.goto("/chatbot/analytics")

  await expect(page.getByRole("alert")).toContainText("analytics unavailable")
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible()
})
