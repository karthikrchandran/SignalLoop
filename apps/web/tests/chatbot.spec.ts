import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("chatbot_demo_mode", "true")
  })
})

test("Chatbot setup and knowledge mockups render with test bot flow", async ({ page }) => {
  await page.goto("/chatbot/channels")

  await expect(page.getByRole("heading", { name: "Channels" })).toBeVisible()
  await expect(page.getByText("Facebook Messenger")).toBeVisible()
  await expect(page.getByText("WhatsApp Business")).toBeVisible()
  await expect(page.getByText("Telegram", { exact: true })).toBeVisible()

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
  await expect(page.getByRole("heading", { name: "Chatbot Dead Letters" })).toBeVisible()
  await expect(page.getByText("wamid.demo.failed")).toBeVisible()
  await page.getByRole("button", { name: "Retry" }).first().click()
  await expect(page.getByText("Dead-lettered message requeued")).toBeVisible()
})
