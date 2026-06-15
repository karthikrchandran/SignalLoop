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
  await page.route("**/api/v1/prospecting/ready-contacts**", async (route) => {
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
            source_channel: "web",
            tags: ["chatbot-lead", "web"],
            intents: ["pricing-request"],
            lead_score: 90,
            priority: "high",
            priority_reasons: [
              "Captured from Messaging Hub",
              "Buyer intent detected",
              "Voice ready",
            ],
            handoff_source: "web",
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
            source_channel: null,
            tags: ["imported"],
            intents: [],
            lead_score: 15,
            priority: "low",
            priority_reasons: ["Company known"],
            handoff_source: null,
            created_at: "2026-06-08T10:00:00Z",
          },
        ],
        count: 2,
      }),
    })
  })

  await page.route(/\/api\/v1\/prospecting\/research(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [
            {
              id: "44444444-4444-4444-8444-444444444444",
              contact_id: "11111111-1111-4111-8111-111111111111",
              company_url: null,
              account_summary: "Previous research noted chatbot pricing intent for Analytical.",
              pain_points: ["Follow up before pricing interest goes cold."],
              objections: ["May need budget approval."],
              personalization_bullets: ["Reference the website chat."],
              suggested_next_action: "Send a short pricing follow-up.",
              email_draft: "Subject: Following up on pricing\n\nHi Ada,",
              voice_opener: "Hi Ada, following up on your pricing question.",
              sources: [{ label: "CRM contact", summary: "Ada at Analytical" }],
              created_at: "2026-06-08T09:30:00Z",
            },
          ],
          count: 1,
        }),
      })
      return
    }

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
        voice_opener: "Hi Ada, this is SignalLoop calling about Analytical.",
        sources: [{ label: "CRM contact", summary: "Ada at Analytical" }],
        created_at: "2026-06-08T10:01:00Z",
      }),
    })
  })

  await page.goto("/prospecting")

  await expect(page.getByRole("heading", { name: "Prospecting" })).toBeVisible()
  await expect(page.getByText("Ready for prospecting")).toBeVisible()
  await expect(page.getByText("High priority").first()).toBeVisible()
  await expect(page.getByText("Score 90").first()).toBeVisible()
  await expect(page.getByText("Messaging Hub").first()).toBeVisible()
  await page.getByLabel("Contact", { exact: true }).selectOption("11111111-1111-4111-8111-111111111111")
  await expect(page.getByText("Previous research noted chatbot pricing intent").first()).toBeVisible()
  await page.getByLabel("Company website").fill("https://analytical.example")
  await page.getByRole("button", { name: "Run research" }).click()

  await expect(page.getByText("Ada Lovelace is a prospect at Analytical").first()).toBeVisible()
  await expect(page.getByText("Subject: Idea for Analytical outreach follow-up")).toBeVisible()
  await expect(page.getByText("Hi Ada, this is SignalLoop calling about Analytical.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Copy email draft" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Copy voice opener" })).toBeVisible()
})

test("bulk researches selected prospects and enrolls them into outreach", async ({ page }) => {
  let bulkCalled = false
  let enrollCalled = false

  await page.route("**/api/v1/prospecting/ready-contacts**", async (route) => {
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
            source_channel: "web",
            tags: ["chatbot-lead", "web"],
            intents: ["pricing-request"],
            lead_score: 90,
            priority: "high",
            priority_reasons: ["Captured from Messaging Hub", "Buyer intent detected"],
            handoff_source: "web",
            created_at: "2026-06-08T10:00:00Z",
          },
          {
            id: "22222222-2222-4222-8222-222222222222",
            workspace_id: "default",
            email: "grace@example.com",
            first_name: "Grace",
            last_name: "Hopper",
            company: "Compiler Co",
            phone: "+15559876543",
            timezone: "UTC",
            source_channel: "whatsapp",
            tags: ["chatbot-lead", "whatsapp"],
            intents: ["demo-request"],
            lead_score: 85,
            priority: "high",
            priority_reasons: ["Captured from Messaging Hub", "Buyer intent detected"],
            handoff_source: "whatsapp",
            created_at: "2026-06-08T10:02:00Z",
          },
        ],
        count: 2,
      }),
    })
  })

  await page.route(/\/api\/v1\/prospecting\/research(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [], count: 0 }),
    })
  })

  await page.route("**/api/v1/prospecting/research/bulk", async (route) => {
    bulkCalled = true
    expect(route.request().method()).toBe("POST")
    const body = route.request().postDataJSON()
    expect(body.contact_ids).toEqual([
      "11111111-1111-4111-8111-111111111111",
      "22222222-2222-4222-8222-222222222222",
    ])
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "33333333-3333-4333-8333-333333333333",
            contact_id: "11111111-1111-4111-8111-111111111111",
            company_url: null,
            account_summary: "Ada bulk research.",
            pain_points: ["Follow up on pricing."],
            objections: ["Needs budget."],
            personalization_bullets: ["Mention pricing."],
            suggested_next_action: "Send outreach.",
            email_draft: "Subject: Ada",
            voice_opener: "Hi Ada.",
            sources: [{ label: "CRM contact", summary: "Ada" }],
            created_at: "2026-06-08T10:03:00Z",
          },
          {
            id: "44444444-4444-4444-8444-444444444444",
            contact_id: "22222222-2222-4222-8222-222222222222",
            company_url: null,
            account_summary: "Grace bulk research.",
            pain_points: ["Follow up on demo."],
            objections: ["Needs timing."],
            personalization_bullets: ["Mention demo."],
            suggested_next_action: "Call today.",
            email_draft: "Subject: Grace",
            voice_opener: "Hi Grace.",
            sources: [{ label: "CRM contact", summary: "Grace" }],
            created_at: "2026-06-08T10:04:00Z",
          },
        ],
        count: 2,
      }),
    })
  })

  await page.route("**/api/v1/campaigns/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [{ id: "camp-1", name: "Q2 Outreach", status: "draft" }],
        count: 1,
      }),
    })
  })

  await page.route("**/api/v1/sequences/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [{ id: "seq-1", campaign_id: "camp-1", name: "Welcome Drip", active: true, created_at: "2026-06-08T10:00:00Z" }],
        count: 1,
      }),
    })
  })

  await page.route("**/api/v1/prospecting/enroll", async (route) => {
    enrollCalled = true
    expect(route.request().method()).toBe("POST")
    const body = route.request().postDataJSON()
    expect(body).toMatchObject({
      contact_ids: [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
      ],
      campaign_id: "camp-1",
      sequence_id: "seq-1",
    })
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        selected_count: 2,
        campaign_added_count: 2,
        campaign_existing_count: 0,
        sequence_enrolled_count: 2,
        sequence_existing_count: 0,
        message: "Added 2 prospects to Q2 Outreach and enrolled 2 in Welcome Drip.",
      }),
    })
  })

  await page.goto("/prospecting")

  await page.getByRole("checkbox", { name: "Select Ada Lovelace - Analytical" }).check()
  await page.getByRole("checkbox", { name: "Select Grace Hopper - Compiler Co" }).check()
  await page.getByRole("button", { name: "Run selected research" }).click()
  await expect(page.getByText("Researched 2 selected prospects.")).toBeVisible()
  expect(bulkCalled).toBe(true)

  await page.getByLabel("Campaign", { exact: true }).selectOption("camp-1")
  await page.getByLabel("Sequence", { exact: true }).selectOption("seq-1")
  await page.getByRole("button", { name: "Add selected to outreach" }).click()

  await expect(page.getByText("Added 2 prospects to Q2 Outreach and enrolled 2 in Welcome Drip.")).toBeVisible()
  expect(enrollCalled).toBe(true)
})
