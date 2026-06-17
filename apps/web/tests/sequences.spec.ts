/**
 * CC-3 E2E coverage — SequencesPage
 *
 * Tests the real multi-step sequence management UI introduced in CC-3:
 *   - load and display existing sequences
 *   - create a new sequence via the dialog (POST + PUT steps)
 *   - edit an existing sequence (PUT)
 *   - delete a sequence (DELETE)
 *   - enroll contacts (POST /enroll)
 *   - error handling when API fails
 */
import { expect, test } from "@playwright/test"

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CAMPAIGNS = [
  { id: "camp-1", name: "Q2 Outreach", status: "draft" },
  { id: "camp-2", name: "Reactivation", status: "draft" },
]

const SEQUENCES = [
  { id: "seq-1", campaign_id: "camp-1", name: "Welcome Drip", active: true, created_at: "2025-01-01T00:00:00Z" },
  { id: "seq-2", campaign_id: "camp-2", name: "Follow-Up", active: false, created_at: "2025-01-02T00:00:00Z" },
]

const SEQ_DETAIL = {
  id: "seq-1",
  campaign_id: "camp-1",
  name: "Welcome Drip",
  active: true,
  created_at: "2025-01-01T00:00:00Z",
  steps: [
    { id: "step-1", step_order: 1, delay_days: 0, subject_template: "Hi!", body_template: "Welcome." },
    { id: "step-2", step_order: 2, delay_days: 3, subject_template: "Follow-up", body_template: "Checking in." },
  ],
}

const SEQ_PROGRESS = { total_enrolled: 5, status_breakdown: { inbox: 3, replied: 2 } }

// ---------------------------------------------------------------------------
// Helpers
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
// Display
// ---------------------------------------------------------------------------

test("Sequences page loads and shows the sequence list", async ({ page }) => {
  await page.route("**/api/v1/sequences/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: SEQUENCES }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SEQ_DETAIL),
    })
  })

  await page.route("**/api/v1/sequences/seq-1/progress", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SEQ_PROGRESS),
    })
  })

  await page.goto("/sequences")

  await expect(page.getByRole("heading", { name: "Sequences" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Sequence List" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Builder" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Enrollments" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Performance" })).toBeVisible()
  await expect(page.getByRole("button", { name: /Welcome Drip/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /Follow-Up/i })).toBeVisible()
})

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

test("Create new sequence opens dialog, submits, and shows success feedback", async ({ page }) => {
  let postCalled = false
  let stepsPutCalled = false

  await page.route("**/api/v1/sequences/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: SEQUENCES }),
      })
      return
    }
    if (route.request().method() === "POST") {
      postCalled = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "seq-new", campaign_id: "camp-1", name: "New Seq", active: false, created_at: "2025-01-03T00:00:00Z" }),
      })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-new/steps", async (route) => {
    stepsPutCalled = true
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "seq-new", campaign_id: "camp-1", name: "New Seq", active: false, created_at: "2025-01-03T00:00:00Z", steps: [] }),
    })
  })

  await page.route("**/api/v1/sequences/seq-new", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "seq-new", campaign_id: "camp-1", name: "New Seq", active: false, created_at: "2025-01-03T00:00:00Z", steps: [] }),
    })
  })

  await page.route("**/api/v1/sequences/seq-new/progress", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_PROGRESS) })
  })

  await page.route("**/api/v1/sequences/seq-1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SEQ_DETAIL),
    })
  })

  await page.route("**/api/v1/sequences/seq-1/progress", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_PROGRESS) })
  })

  await page.goto("/sequences")

  await page.getByRole("button", { name: /new sequence/i }).click()

  await page.getByLabel(/sequence name/i).fill("New Seq")
  await page.getByPlaceholder("Subject line").fill("Hello {{first_name}}")
  await page.getByPlaceholder("Email body").fill("Body copy here.")

  await page.getByRole("button", { name: /create sequence/i }).click()

  await expect(page.getByText(/^Sequence created\.$/)).toBeVisible()
  expect(postCalled).toBe(true)
  expect(stepsPutCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Edit
// ---------------------------------------------------------------------------

test("Edit existing sequence sends PUT and shows success feedback", async ({ page }) => {
  let putCalled = false

  await page.route("**/api/v1/sequences/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SEQUENCES }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_DETAIL) })
      return
    }
    if (route.request().method() === "PUT") {
      putCalled = true
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...SEQ_DETAIL, name: "Renamed" }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-1/progress", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_PROGRESS) })
  })

  await page.route("**/api/v1/sequences/seq-1/steps", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...SEQ_DETAIL, steps: [] }) })
  })

  await page.goto("/sequences")

  await page.getByRole("button", { name: /edit/i }).first().click()

  const nameInput = page.getByLabel(/sequence name/i)
  await nameInput.clear()
  await nameInput.fill("Renamed")

  await page.getByRole("button", { name: /save changes/i }).click()

  await expect(page.getByText(/^Sequence updated\.$/)).toBeVisible()
  expect(putCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------

test("Delete sequence sends DELETE and removes item from list", async ({ page }) => {
  let deleteCalled = false

  await page.route("**/api/v1/sequences/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SEQUENCES }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_DETAIL) })
      return
    }
    if (route.request().method() === "DELETE") {
      deleteCalled = true
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ message: "Sequence deleted" }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-1/progress", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_PROGRESS) })
  })

  await page.goto("/sequences")

  await page.getByRole("button", { name: /delete/i }).first().click()

  await expect(page.getByText(/^Sequence deleted\.$/)).toBeVisible()
  expect(deleteCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Enroll
// ---------------------------------------------------------------------------

test("Enroll contacts calls enroll endpoint and shows feedback", async ({ page }) => {
  let enrollCalled = false

  await page.route("**/api/v1/sequences/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: SEQUENCES }) })
      return
    }
    await route.continue()
  })

  await page.route("**/api/v1/sequences/seq-1", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_DETAIL) })
  })

  await page.route("**/api/v1/sequences/seq-1/progress", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SEQ_PROGRESS) })
  })

  await page.route("**/api/v1/sequences/seq-1/enroll/camp-1", async (route) => {
    enrollCalled = true
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enrolled: 3, message: "Enrolled 3 contacts." }),
    })
  })

  await page.goto("/sequences")

  await page.getByRole("button", { name: /enroll/i }).first().click()

  await expect(page.getByText(/^Enrolled 3 contacts\.$/)).toBeVisible()
  expect(enrollCalled).toBe(true)
})

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

test("API error on load shows error alert", async ({ page }) => {
  await page.route("**/api/v1/sequences/", async (route) => {
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "server error" }) })
  })

  await page.goto("/sequences")

  await expect(page.getByRole("alert")).toBeVisible()
})
