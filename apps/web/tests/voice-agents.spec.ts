/**
 * CC-4 E2E coverage — VoiceAgentsPage (scripts management)
 *
 * Tests the backend-backed script management UI introduced in CC-4:
 *   - load and display scripts filtered by campaign
 *   - compact readiness notice for voice prerequisites
 *   - create a new script (POST)
 *   - edit a script (PUT)
 *   - deactivate (DELETE)
 *   - error handling when prerequisites are missing
 */
import { expect, test } from "@playwright/test"

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CAMPAIGNS = [
  { id: "camp-1", name: "Q2 Outreach", status: "draft" },
  { id: "camp-2", name: "Reactivation", status: "draft" },
]

const SCRIPTS = [
  {
    id: "script-1",
    campaign_id: "camp-1",
    name: "Pitch v1",
    active: true,
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "script-2",
    campaign_id: "camp-1",
    name: "Pitch v2",
    active: false,
    created_at: "2025-01-02T00:00:00Z",
  },
]

const SCRIPT_DETAIL = {
  id: "script-1",
  campaign_id: "camp-1",
  name: "Pitch v1",
  active: true,
  created_at: "2025-01-01T00:00:00Z",
  content:
    "## Opening Pitch\nHi!\n\n## Q&A\nQ: Available?\nA: Yes.\n\n## Fallback\nI'll follow up.\n\n## Scheduling\nWhen are you free?",
  parsed: {
    opening_pitch: "Hi!",
    fallback_response: "I'll follow up.",
    scheduling_question: "When are you free?",
    qa_pairs: [{ question: "Available?", answer: "Yes." }],
  },
}

const CALL_PREP = {
  id: "prep-1",
  contact_id: "contact-1",
  company_url: "https://analytical.example",
  account_summary:
    "Ada Lovelace is evaluating SignalLoop after a website pricing chat.",
  pain_points: ["Keep the voice follow-up aligned to chat and CRM history."],
  objections: ["May need pricing clarity before booking a demo."],
  personalization_bullets: ["Reference the website pricing chat."],
  suggested_next_action: "Call with the pricing-context opener.",
  email_draft: "Subject: Pricing follow-up\n\nHi Ada,",
  voice_opener:
    "Hi Ada, I am calling about your pricing question for Analytical.",
  sources: [{ label: "CRM contact", summary: "Ada at Analytical" }],
  created_at: "2026-06-08T10:01:00Z",
}

const CALLS = {
  data: [
    {
      call_request_id: "call-1",
      contact_id: "contact-1",
      campaign_id: "camp-1",
      status: "completed",
      outcome: "answered",
      duration_seconds: 96,
      scheduled_at: "2026-06-08T10:05:00Z",
      created_at: "2026-06-08T10:04:00Z",
    },
  ],
  count: 1,
}

const CALL_DETAIL = {
  call_request_id: "call-1",
  contact_id: "contact-1",
  campaign_id: "camp-1",
  status: "completed",
  trigger_reason: "manual_test_call",
  outcome: "answered",
  duration_seconds: 96,
  recording_url: null,
  transcript:
    "Ada said they are interested but need pricing clarity before booking the demo next Tuesday.",
  unanswered_questions: ["pricing clarity before booking a demo"],
  scheduling_interest: true,
  scheduled_at: "2026-06-08T10:05:00Z",
  intelligence: {
    summary: "Buyer showed interest and needs pricing clarity before booking.",
    sentiment: "positive",
    objection: "pricing clarity before booking a demo",
    next_action: "Book the requested meeting time.",
    recommended_follow_up:
      "Send a pricing-focused follow-up, then confirm the demo time.",
  },
}

const SETUP_CONFIGURED: object = {
  callbacks: {
    public_host: true,
    public_base_url: "https://example.ngrok.io",
    twilio_twiml_url: "https://example.ngrok.io/api/v1/voice/call",
    twilio_media_stream_url: "wss://example.ngrok.io/api/v1/voice/stream",
  },
  integrations: [
    {
      key: "sms",
      label: "SMS: Twilio SMS",
      capability: "sms",
      provider: "twilio",
      provider_label: "Twilio SMS",
      configured: true,
      source: "env",
      note: null,
    },
    {
      key: "voice",
      label: "VOICE: Twilio Voice",
      capability: "voice",
      provider: "twilio",
      provider_label: "Twilio Voice",
      configured: true,
      source: "env",
      note: null,
    },
    {
      key: "stt",
      label: "STT: Deepgram Nova-2",
      capability: "stt",
      provider: "deepgram",
      provider_label: "Deepgram Nova-2",
      configured: true,
      source: "env",
      note: null,
    },
    {
      key: "tts",
      label: "TTS: Deepgram Aura",
      capability: "tts",
      provider: "deepgram",
      provider_label: "Deepgram Aura",
      configured: true,
      source: "env",
      note: null,
    },
    {
      key: "llm",
      label: "LLM: Groq",
      capability: "llm",
      provider: "groq",
      provider_label: "Groq",
      configured: true,
      source: "env",
      note: null,
    },
  ],
}

const SETUP_MISSING: object = {
  callbacks: {
    public_host: false,
    public_base_url: "",
    twilio_twiml_url: "",
    twilio_media_stream_url: "",
  },
  integrations: [
    {
      key: "sms",
      label: "SMS: Twilio SMS",
      capability: "sms",
      provider: "twilio",
      provider_label: "Twilio SMS",
      configured: true,
      source: "env",
      note: null,
    },
    {
      key: "voice",
      label: "VOICE: Twilio Voice",
      capability: "voice",
      provider: "twilio",
      provider_label: "Twilio Voice",
      configured: false,
      source: "missing",
      note: null,
    },
    {
      key: "stt",
      label: "STT: Deepgram Nova-2",
      capability: "stt",
      provider: "deepgram",
      provider_label: "Deepgram Nova-2",
      configured: false,
      source: "missing",
      note: null,
    },
    {
      key: "tts",
      label: "TTS: Deepgram Aura",
      capability: "tts",
      provider: "deepgram",
      provider_label: "Deepgram Aura",
      configured: false,
      source: "missing",
      note: null,
    },
    {
      key: "llm",
      label: "LLM: Groq",
      capability: "llm",
      provider: "groq",
      provider_label: "Groq",
      configured: false,
      source: "missing",
      note: null,
    },
  ],
}

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------

test.use({ storageState: { cookies: [], origins: [] } })

let queuedTestCallPayload: unknown | null = null

test.beforeEach(async ({ page }) => {
  queuedTestCallPayload = null

  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "ws-e2e")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "admin@example.com",
        full_name: "Admin",
        is_superuser: true,
      }),
    })
  })

  await page.route("**/api/v1/campaigns/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: CAMPAIGNS }),
    })
  })

  await page.route("**/api/v1/prospecting/research**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [CALL_PREP], count: 1 }),
    })
  })

  await page.route("**/api/v1/calls/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (request.method() === "GET" && url.pathname.endsWith("/api/v1/calls/")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CALLS),
      })
      return
    }

    if (
      request.method() === "GET" &&
      url.pathname.endsWith("/api/v1/calls/call-1")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CALL_DETAIL),
      })
      return
    }

    if (
      request.method() === "POST" &&
      url.pathname.endsWith("/api/v1/calls/test-call")
    ) {
      queuedTestCallPayload = request.postDataJSON()
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          call_request_id: "call-test-1",
          status: "queued",
          message: "Test call queued",
        }),
      })
      return
    }

    await route.continue()
  })
})

// ---------------------------------------------------------------------------
// Display + readiness notice
// ---------------------------------------------------------------------------

test("Voice Agents page shows profiles, language support, and scripts when fully configured", async ({
  page,
}) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: SCRIPTS, count: 2 }),
    })
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SCRIPT_DETAIL),
    })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_CONFIGURED),
    })
  })

  await page.goto("/voice-agents")

  await expect(
    page.getByRole("heading", { name: "Voice Agents" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Select Alex voice profile" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Select Morgan voice profile" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Select Rajesh voice profile" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Select Priya voice profile" }),
  ).toBeVisible()
  await expect(page.getByLabel("Voice language")).toContainText("English")
  await page.getByLabel("Voice language").click()
  await page.getByRole("option", { name: "Hindi" }).click()
  await expect(page.getByLabel("Voice language")).toContainText("Hindi")
  await expect(page.getByRole("button", { name: /Pitch v1/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /Pitch v2/i })).toBeVisible()
  await expect(page.getByText("Prospecting call prep")).toBeVisible()
  await expect(
    page.getByText("Ada Lovelace is evaluating SignalLoop"),
  ).toBeVisible()
  await expect(
    page.getByText("Hi Ada, I am calling about your pricing question"),
  ).toBeVisible()
  await expect(page.getByText("Voice readiness needs setup")).toBeHidden()
  await expect(page.getByText("Voice execution")).toBeVisible()
  await expect(page.getByText("Selected provider")).toBeVisible()
  await expect(page.getByText("Twilio Voice").first()).toBeVisible()
  await expect(page.getByText("Call outcome intelligence")).toBeVisible()
  await expect(
    page.getByText("Buyer showed interest and needs pricing clarity"),
  ).toBeVisible()
  await page.getByRole("button", { name: "Queue test call" }).click()
  await expect(page.getByText(/^Test call queued\.$/)).toBeVisible()
  expect(queuedTestCallPayload).toEqual({
    contact_id: "contact-1",
    campaign_id: "camp-1",
    voice_script_id: "script-1",
  })
  await expect(page.getByText("Twilio SMS")).toBeHidden()
})

test("Readiness notice links to provider setup when voice prerequisites are not configured", async ({
  page,
}) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [], count: 0 }),
    })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_MISSING),
    })
  })

  await page.goto("/voice-agents")

  await expect(page.getByText("Voice readiness needs setup")).toBeVisible()
  await expect(page.getByText(/Twilio Voice/).first()).toBeVisible()
  await expect(page.getByText(/Deepgram Nova-2/)).toBeVisible()
  await expect(page.getByText(/Groq/)).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Configure providers" }),
  ).toHaveAttribute("href", "/settings/providers")
  await expect(page.getByText("Twilio SMS")).toBeHidden()
})

test("New Hindi script uses the selected Indian persona and language", async ({
  page,
}) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: SCRIPTS, count: 2 }),
    })
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SCRIPT_DETAIL),
    })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_CONFIGURED),
    })
  })

  await page.goto("/voice-agents")

  await page
    .getByRole("button", { name: "Select Rajesh voice profile" })
    .click()
  await page.getByLabel("Voice language").click()
  await page.getByRole("option", { name: "Hindi" }).click()
  await page.getByRole("button", { name: /new script/i }).click()

  await expect(page.getByLabel(/script name/i)).toHaveValue(
    "Rajesh Hindi campaign script",
  )
  await expect(page.getByLabel(/script content/i)).toHaveValue(/Namaste/)
  await expect(page.getByLabel(/script content/i)).toHaveValue(/Rajesh/)
})

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

test("Create new script opens dialog, submits POST, and shows success feedback", async ({
  page,
}) => {
  let postCalled = false

  await page.route("**/api/v1/scripts/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: SCRIPTS, count: 2 }),
      })
      return
    }
    if (route.request().method() === "POST") {
      postCalled = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "script-new",
          campaign_id: "camp-1",
          name: "New Script",
          active: true,
          created_at: "2025-01-03T00:00:00Z",
        }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SCRIPT_DETAIL),
    })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_CONFIGURED),
    })
  })

  await page.goto("/voice-agents")

  await page.getByRole("button", { name: /new script/i }).click()

  await page.getByLabel(/script name/i).fill("New Script")

  await page.getByRole("button", { name: /create script/i }).click()

  await expect(page.getByText(/^Script created\.$/)).toBeVisible()
  expect(postCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Edit
// ---------------------------------------------------------------------------

test("Edit existing script sends PUT and shows success feedback", async ({
  page,
}) => {
  let putCalled = false

  await page.route("**/api/v1/scripts/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: SCRIPTS, count: 2 }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SCRIPT_DETAIL),
      })
      return
    }
    if (route.request().method() === "PUT") {
      putCalled = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...SCRIPT_DETAIL, name: "Renamed Script" }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_CONFIGURED),
    })
  })

  await page.goto("/voice-agents")

  await page.getByRole("button", { name: /edit/i }).first().click()

  const nameInput = page.getByLabel(/script name/i)
  await nameInput.clear()
  await nameInput.fill("Renamed Script")

  await page.getByRole("button", { name: /save changes/i }).click()

  await expect(page.getByText(/^Script updated\.$/)).toBeVisible()
  expect(putCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Delete (soft-deactivate)
// ---------------------------------------------------------------------------

test("Deactivate script sends DELETE and shows feedback", async ({ page }) => {
  let deleteCalled = false

  await page.route("**/api/v1/scripts/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: SCRIPTS, count: 2 }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SCRIPT_DETAIL),
      })
      return
    }
    if (route.request().method() === "DELETE") {
      deleteCalled = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Script deactivated" }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_CONFIGURED),
    })
  })

  await page.goto("/voice-agents")

  await page
    .getByRole("button", { name: /deactivate|delete/i })
    .first()
    .click()

  await expect(page.getByText(/^Script deactivated\.$/)).toBeVisible()
  expect(deleteCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

test("API error on voice page load shows error alert", async ({ page }) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "server error" }),
    })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SETUP_MISSING),
    })
  })

  await page.goto("/voice-agents")

  await expect(page.getByRole("alert")).toBeVisible()
})
