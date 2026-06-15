import { expect, test } from "@playwright/test"

const OVERVIEW = {
  generated_at: "2026-06-08T11:00:00Z",
  next_best_actions: [
    {
      id: "nba-voice-call-1",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      company: "Analytical",
      channel: "voice",
      priority: "high",
      score: 95,
      title: "Book meeting from voice call",
      reason:
        "Ada asked for implementation pricing clarity after an answered call.",
      recommended_action: "Book the requested meeting time.",
      source: "voice",
    },
    {
      id: "nba-chat-chat-1",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      company: "Analytical",
      channel: "chatbot",
      priority: "high",
      score: 90,
      title: "Reply to escalated chatbot thread",
      reason: "Pricing question needs a human.",
      recommended_action:
        "Open the thread and answer the buyer's pricing question.",
      source: "chatbot",
    },
  ],
  unified_inbox: [
    {
      id: "chatbot-chat-1",
      source: "chatbot",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      title: "Chatbot escalation",
      summary: "Can you explain pricing and implementation?",
      priority: "high",
      status: "escalated",
      action_label: "Reply in inbox",
      next_best_action:
        "Open the thread and answer the buyer's pricing question.",
      created_at: "2026-06-08T10:30:00Z",
    },
    {
      id: "voice-call-1",
      source: "voice",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      title: "Voice follow-up",
      summary: "Ada is interested but needs implementation pricing clarity.",
      priority: "high",
      status: "answered",
      action_label: "Schedule meeting",
      next_best_action: "Book the requested meeting time.",
      created_at: "2026-06-08T10:20:00Z",
    },
  ],
  journey: {
    stages: [
      {
        id: "chatbot_capture",
        label: "Chatbot capture",
        count: 1,
        description: "Leads or escalations captured by Messaging Hub.",
      },
      {
        id: "prospecting_research",
        label: "Prospecting research",
        count: 1,
        description: "Contacts with AI research and outreach drafts.",
      },
      {
        id: "sequence_enrollment",
        label: "Sequence enrollment",
        count: 1,
        description: "Contacts actively enrolled in outreach sequences.",
      },
      {
        id: "voice_follow_up",
        label: "Voice follow-up",
        count: 1,
        description: "Contacts with voice call activity.",
      },
      {
        id: "sales_handoff",
        label: "Sales handoff",
        count: 1,
        description: "Contacts needing human follow-up.",
      },
    ],
    edges: [
      {
        from_stage: "chatbot_capture",
        to_stage: "prospecting_research",
        label: "Research captured lead",
        count: 1,
      },
      {
        from_stage: "prospecting_research",
        to_stage: "sequence_enrollment",
        label: "Enroll in outreach",
        count: 1,
      },
    ],
  },
  knowledge_gaps: [
    {
      id: "gap-pricing",
      title: "Pricing clarity",
      source: "chatbot",
      evidence_count: 2,
      evidence: ["Can you explain pricing and implementation?"],
      recommended_fix:
        "Add pricing and implementation FAQ entries to the shared knowledge base.",
      priority: "high",
    },
  ],
  offer_recommendations: [
    {
      id: "offer-starter",
      title: "Use Starter Demo Pack",
      reason: "Pricing and implementation questions are active.",
      recommended_offer: "Starter Demo Pack",
      priority: "high",
    },
  ],
  experiment_recommendations: [
    {
      id: "experiment-pricing",
      title: "Pricing clarity holdout test",
      hypothesis:
        "Adding pricing clarity content will reduce human escalations from high-intent chatbot leads.",
      primary_metric: "Escalation rate",
      variants: ["Current answer", "Pricing clarity answer"],
      holdout_percent: 10,
      eligible_count: 2,
      status: "ready",
    },
  ],
  audit_replay: [
    {
      id: "audit-1",
      event_name: "prospect.researched",
      resource_type: "prospecting_snapshot",
      resource_id: "contact-2",
      actor_role: "admin",
      summary: "Generated Compiler Co research and outreach draft.",
      created_at: "2026-06-08T10:10:00Z",
      payload: {
        summary: "Generated Compiler Co research and outreach draft.",
      },
    },
  ],
  provider_health: [
    {
      id: "provider-sendgrid-email",
      provider: "sendgrid",
      channel: "email",
      status: "needs_attention",
      success_count: 1,
      failure_count: 2,
      last_event_at: "2026-06-08T10:05:00Z",
      recommended_action:
        "Review failed sendgrid delivery events and retry blocked contacts.",
    },
  ],
  pipeline_risks: [
    {
      id: "risk-contact-1",
      contact_id: "contact-1",
      contact_name: "Ada Lovelace",
      company: "Analytical",
      risk_level: "high",
      risk_score: 100,
      reasons: [
        "Open chatbot escalation",
        "Answered voice call is waiting for scheduling",
        "Failed email send",
        "Stalled active sequence",
        "Engaged contact has no recent action",
      ],
      recommended_action:
        "Resolve the escalation, repair delivery, and schedule the requested meeting.",
    },
  ],
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
        email: "admin@example.com",
        full_name: "Admin User",
        is_superuser: true,
      }),
    })
  })

  await page.route(
    "**/api/v1/engagement-intelligence/overview",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(OVERVIEW),
      })
    },
  )
})

test("SignalLoop AI shows actions, unified inbox, journey canvas, and recommendations", async ({
  page,
}) => {
  await page.goto("/signalloop-ai")

  await expect(
    page.getByRole("heading", { name: "SignalLoop AI" }),
  ).toBeVisible()
  await expect(page.getByText("Next Best Actions")).toBeVisible()
  await expect(page.getByText("Book meeting from voice call")).toBeVisible()
  await expect(
    page.getByText("Reply to escalated chatbot thread"),
  ).toBeVisible()
  await expect(page.getByText("Unified work queue")).toBeVisible()
  await expect(
    page.getByText("Chatbot escalation", { exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Voice follow-up").first()).toBeVisible()
  await expect(page.getByText("Journey orchestration canvas")).toBeVisible()
  await expect(page.getByText("Chatbot capture")).toBeVisible()
  await expect(page.getByText("Sequence enrollment")).toBeVisible()
  await expect(page.getByText("Knowledge gap finder")).toBeVisible()
  await expect(page.getByText("Pricing clarity", { exact: true })).toBeVisible()
  await expect(page.getByText("Offer recommendations")).toBeVisible()
  await expect(page.getByText("Use Starter Demo Pack")).toBeVisible()
  await expect(page.getByText("Experiment and holdout testing")).toBeVisible()
  await expect(page.getByText("Pricing clarity holdout test")).toBeVisible()
  await expect(page.getByText("Compliance replay")).toBeVisible()
  await expect(page.getByText("prospect.researched")).toBeVisible()
  await expect(page.getByText("Provider command center")).toBeVisible()
  await expect(page.getByText("sendgrid", { exact: true })).toBeVisible()
  await expect(page.getByText("Pipeline risk view")).toBeVisible()
  await expect(page.getByText("Ada Lovelace").first()).toBeVisible()
})
