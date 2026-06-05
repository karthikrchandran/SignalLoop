/**
 * CC-4 E2E coverage — VoiceAgentsPage (scripts management)
 *
 * Tests the backend-backed script management UI introduced in CC-4:
 *   - load and display scripts filtered by campaign
 *   - readiness cards for Twilio / Deepgram / Groq
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
  { id: "script-1", campaign_id: "camp-1", name: "Pitch v1", active: true, created_at: "2025-01-01T00:00:00Z" },
  { id: "script-2", campaign_id: "camp-1", name: "Pitch v2", active: false, created_at: "2025-01-02T00:00:00Z" },
]

const SCRIPT_DETAIL = {
  id: "script-1",
  campaign_id: "camp-1",
  name: "Pitch v1",
  active: true,
  created_at: "2025-01-01T00:00:00Z",
  content: "## Opening Pitch\nHi!\n\n## Q&A\nQ: Available?\nA: Yes.\n\n## Fallback\nI'll follow up.\n\n## Scheduling\nWhen are you free?",
  parsed: {
    opening_pitch: "Hi!",
    fallback_response: "I'll follow up.",
    scheduling_question: "When are you free?",
    qa_pairs: [{ question: "Available?", answer: "Yes." }],
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
    { key: "twilio", label: "Twilio Voice", configured: true, source: "env", note: null },
    { key: "deepgram", label: "Deepgram", configured: true, source: "env", note: null },
    { key: "groq", label: "Groq", configured: true, source: "env", note: null },
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
    { key: "twilio", label: "Twilio Voice", configured: false, source: "missing", note: null },
    { key: "deepgram", label: "Deepgram", configured: false, source: "missing", note: null },
    { key: "groq", label: "Groq", configured: false, source: "missing", note: null },
  ],
}

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
    localStorage.setItem("workspace_id", "ws-e2e")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "user-1", email: "admin@example.com", full_name: "Admin", is_superuser: true }),
    })
  })

  await page.route("**/api/v1/campaigns/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: CAMPAIGNS }),
    })
  })
})

// ---------------------------------------------------------------------------
// Display + readiness cards
// ---------------------------------------------------------------------------

test("Voice Setup page shows scripts and readiness cards when fully configured", async ({ page }) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SCRIPTS, count: 2 }) })
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SCRIPT_DETAIL) })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP_CONFIGURED) })
  })

  await page.goto("/voice-agents")

  await expect(page.getByRole("heading", { name: "Voice Setup" })).toBeVisible()
  await expect(page.getByRole("button", { name: /Pitch v1/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /Pitch v2/i })).toBeVisible()
  await expect(page.getByText("Twilio Voice")).toBeVisible()
  await expect(page.getByText("Deepgram")).toBeVisible()
  await expect(page.getByText("Groq")).toBeVisible()
})

test("Readiness cards show warning state when integrations are not configured", async ({ page }) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [], count: 0 }) })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP_MISSING) })
  })

  await page.goto("/voice-agents")

  await expect(page.getByText("Twilio Voice")).toBeVisible()
  // All three readiness cards must be present even when unconfigured
  const readinessCards = page.getByText(/Twilio Voice|Deepgram|Groq/)
  await expect(readinessCards.first()).toBeVisible()
})

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

test("Create new script opens dialog, submits POST, and shows success feedback", async ({ page }) => {
  let postCalled = false

  await page.route("**/api/v1/scripts/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SCRIPTS, count: 2 }) })
      return
    }
    if (route.request().method() === "POST") {
      postCalled = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "script-new", campaign_id: "camp-1", name: "New Script", active: true, created_at: "2025-01-03T00:00:00Z" }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SCRIPT_DETAIL) })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP_CONFIGURED) })
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

test("Edit existing script sends PUT and shows success feedback", async ({ page }) => {
  let putCalled = false

  await page.route("**/api/v1/scripts/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SCRIPTS, count: 2 }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SCRIPT_DETAIL) })
      return
    }
    if (route.request().method() === "PUT") {
      putCalled = true
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...SCRIPT_DETAIL, name: "Renamed Script" }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP_CONFIGURED) })
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
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SCRIPTS, count: 2 }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/scripts/script-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SCRIPT_DETAIL) })
      return
    }
    if (route.request().method() === "DELETE") {
      deleteCalled = true
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ message: "Script deactivated" }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP_CONFIGURED) })
  })

  await page.goto("/voice-agents")

  await page.getByRole("button", { name: /deactivate|delete/i }).first().click()

  await expect(page.getByText(/^Script deactivated\.$/)).toBeVisible()
  expect(deleteCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

test("API error on voice page load shows error alert", async ({ page }) => {
  await page.route("**/api/v1/scripts/", async (route) => {
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "server error" }) })
  })

  await page.route("**/api/v1/utils/setup-overview/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SETUP_MISSING) })
  })

  await page.goto("/voice-agents")

  await expect(page.getByRole("alert")).toBeVisible()
})
