import { expect, type Route, test } from "@playwright/test"

const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
const ACME_ACCOUNT_ID = "22222222-2222-4222-8222-222222222222"
const NEW_ACCOUNT_ID = "33333333-3333-4333-8333-333333333333"
const TURING_CONTACT_ID = "44444444-4444-4444-8444-444444444444"

function accountRow(overrides: Record<string, unknown> = {}) {
  return {
    id: ACCOUNT_ID,
    workspace_id: "default",
    name: "Analytical Health",
    account_key: "analytical-health",
    website_url: null,
    industry: "Healthcare",
    status: "active",
    summary: "Analytical Health is evaluating cross-channel outreach.",
    tags: ["healthcare"],
    created_at: "2026-06-08T10:00:00Z",
    updated_at: "2026-06-08T10:00:00Z",
    contact_count: 2,
    last_activity_at: "2026-06-08T10:30:00Z",
    channel_counts: {
      chatbot: 1,
      email: 0,
      voice: 1,
      prospecting: 0,
    },
    top_next_action: "Reply with pricing clarity, then queue a call.",
    ...overrides,
  }
}

function accountsResponse(account: Record<string, unknown>) {
  return {
    data: [account],
    count: 1,
  }
}

function accountProfile(overrides: Record<string, unknown> = {}) {
  return {
    account: {
      id: ACCOUNT_ID,
      workspace_id: "default",
      name: "Analytical Health",
      account_key: "analytical-health",
      website_url: null,
      industry: "Healthcare",
      status: "active",
      summary: "Multi-location healthcare buyer.",
      tags: ["pricing", "voice-ready"],
      created_at: "2026-06-08T10:00:00Z",
      updated_at: "2026-06-08T10:00:00Z",
      ...(overrides.account as Record<string, unknown> | undefined),
    },
    contacts: [
      {
        id: "contact-ada",
        workspace_id: "default",
        account_id: ACCOUNT_ID,
        email: "ada@analytical.health",
        first_name: "Ada",
        last_name: "Lovelace",
        company: "Analytical Health",
        phone: "+1555010101",
        timezone: "America/New_York",
        created_at: "2026-06-08T10:10:00Z",
        display_name: "Ada Lovelace",
      },
      {
        id: "contact-grace",
        workspace_id: "default",
        account_id: ACCOUNT_ID,
        email: "grace@analytical.health",
        first_name: "Grace",
        last_name: "Hopper",
        company: "Analytical Health",
        phone: "+1555010102",
        timezone: "America/New_York",
        created_at: "2026-06-08T10:20:00Z",
        display_name: "Grace Hopper",
      },
    ],
    channel_summaries: {
      chatbot: {
        channel: "chatbot",
        label: "Chatbot",
        count: 1,
        status: "Active",
        detail: "Escalation captured from buyer chat.",
      },
      email: {
        channel: "email",
        label: "Email",
        count: 1,
        status: "Ready",
        detail: "Pricing follow-up drafted.",
      },
      voice: {
        channel: "voice",
        label: "Voice",
        count: 1,
        status: "Complete",
        detail: "Call completed with decision maker.",
      },
      prospecting: {
        channel: "prospecting",
        label: "Prospecting",
        count: 1,
        status: "Queued",
        detail: "Brief refreshed from account signals.",
      },
    },
    next_best_action: {
      title: "Reply with pricing clarity, then queue a call",
      reason: "The buyer asked for pricing and is ready for a voice follow-up.",
      source: "voice",
      priority: "high",
    },
    open_work: [
      {
        id: "work-chatbot-escalation",
        source: "chatbot",
        title: "Chatbot escalation",
        contact_id: "contact-ada",
        contact_name: "Ada Lovelace",
        status: "open",
        created_at: "2026-06-08T11:00:00Z",
      },
    ],
    prospecting_brief: {
      snapshot_id: "snapshot-analytical-health",
      contact_id: "contact-ada",
      account_summary:
        "Analytical Health is evaluating cross-channel outreach.",
      suggested_next_action: "Send pricing clarity and offer a voice call.",
      email_draft_available: true,
      voice_opener_available: true,
      created_at: "2026-06-08T11:30:00Z",
    },
    timeline: [
      {
        id: "timeline-voice-call",
        source: "voice",
        event_type: "call.completed",
        title: "Voice call completed",
        detail: "Pricing question needs a human",
        contact_id: "contact-ada",
        contact_name: "Ada Lovelace",
        timestamp: "2026-06-08T12:00:00Z",
      },
    ],
    ...Object.fromEntries(
      Object.entries(overrides).filter(([key]) => key !== "account"),
    ),
  }
}

function contactResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: TURING_CONTACT_ID,
    workspace_id: "default",
    account_id: null,
    email: "alan@analytical.health",
    first_name: "Alan",
    last_name: "Turing",
    company: "Analytical Health",
    phone: "+1555010103",
    timezone: "Europe/London",
    created_at: "2026-06-08T10:40:00Z",
    ...overrides,
  }
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
})

test("shows Customer 360 accounts with channel rollups", async ({ page }) => {
  await page.route("**/api/v1/customer-360/accounts**", async (route) => {
    const url = new URL(route.request().url())

    if (
      url.pathname === `/api/v1/customer-360/accounts/${ACCOUNT_ID}` ||
      url.pathname.endsWith(`/customer-360/accounts/${ACCOUNT_ID}`)
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(accountProfile()),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(accountsResponse(accountRow())),
    })
  })

  await page.goto("/customer-360")

  await expect(
    page.getByRole("heading", { name: "Customer 360" }),
  ).toBeVisible()
  await expect(page.getByText("Analytical Health")).toBeVisible()
  await expect(page.getByText("2 contacts")).toBeVisible()
  await expect(page.getByText("Chatbot 1")).toBeVisible()
  await expect(page.getByText("Voice 1")).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Open Analytical Health" }),
  ).toHaveAttribute("href", `/customer-360/${ACCOUNT_ID}`)

  await page.getByRole("link", { name: "Open Analytical Health" }).click()

  await expect(page).toHaveURL(new RegExp(`/customer-360/${ACCOUNT_ID}$`))
  await expect(
    page.getByRole("heading", { name: "Analytical Health" }),
  ).toBeVisible()
  await expect(page.getByText("Multi-location healthcare buyer.")).toBeVisible()
})

test("shows a Customer 360 account profile", async ({ page }) => {
  await page.route(
    `**/api/v1/customer-360/accounts/${ACCOUNT_ID}`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(accountProfile()),
      })
    },
  )

  await page.goto(`/customer-360/${ACCOUNT_ID}`)

  await expect(
    page.getByRole("heading", { name: "Analytical Health" }),
  ).toBeVisible()
  await expect(page.getByText("Multi-location healthcare buyer.")).toBeVisible()
  await expect(
    page.getByText("Ada Lovelace", { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByText("Grace Hopper", { exact: true })).toBeVisible()
  await expect(page.getByText("Chatbot", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Email", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Voice", { exact: true }).first()).toBeVisible()
  await expect(
    page.getByText("Prospecting", { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByText("Reply with pricing clarity, then queue a call"),
  ).toBeVisible()
  await expect(page.getByText("Unified account timeline")).toBeVisible()
  await expect(page.getByText("Voice call completed")).toBeVisible()
  await expect(page.getByText("Pricing question needs a human")).toBeVisible()
})

test("keeps searched accounts when the initial list response finishes later", async ({
  page,
}) => {
  let initialRoute: Route | undefined
  let searchedRoute: Route | undefined
  let resolveInitialRoute: (() => void) | undefined
  let resolveSearchedRoute: (() => void) | undefined
  const initialRouteReady = new Promise<void>((resolve) => {
    resolveInitialRoute = resolve
  })
  const searchedRouteReady = new Promise<void>((resolve) => {
    resolveSearchedRoute = resolve
  })

  await page.route("**/api/v1/customer-360/accounts**", (route) => {
    const url = new URL(route.request().url())
    expect(url.searchParams.get("limit")).toBe("50")

    if (url.searchParams.has("search")) {
      expect(url.searchParams.get("search")).toBe("Acme")
      searchedRoute = route
      resolveSearchedRoute?.()
      return
    }

    expect(url.searchParams.has("search")).toBe(false)
    initialRoute = route
    resolveInitialRoute?.()
  })

  await page.goto("/customer-360")
  await initialRouteReady

  await page.getByPlaceholder("Search accounts").fill("Acme  ")
  await page.getByPlaceholder("Search accounts").press("Enter")
  await searchedRouteReady

  if (!searchedRoute) throw new Error("Search request was not captured")
  await searchedRoute.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(
      accountsResponse(
        accountRow({
          id: ACME_ACCOUNT_ID,
          name: "Acme Ventures",
          account_key: "acme-ventures",
          industry: "Manufacturing",
          contact_count: 1,
          channel_counts: {
            chatbot: 0,
            email: 1,
            voice: 0,
            prospecting: 1,
          },
          top_next_action: "Send Acme the implementation follow-up.",
        }),
      ),
    ),
  })

  await expect(page.getByText("Acme Ventures")).toBeVisible()

  if (!initialRoute) throw new Error("Initial request was not captured")
  await initialRoute.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(accountsResponse(accountRow())),
  })
  await page.waitForTimeout(250)

  await expect(page.getByText("Acme Ventures")).toBeVisible()
  await expect(page.getByText("Analytical Health")).not.toBeVisible()
})

test("creates a new Customer 360 account and opens the new profile", async ({
  page,
}) => {
  let createPayload: Record<string, unknown> | undefined

  await page.route("**/api/v1/customer-360/accounts**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [], count: 0 }),
    })
  })

  await page.route("**/api/v1/accounts", async (route) => {
    expect(route.request().method()).toBe("POST")
    createPayload = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(
        accountRow({
          id: NEW_ACCOUNT_ID,
          name: "Analytical Health",
          account_key: "analytical-health",
          website_url: "https://analytical.health",
          industry: "Healthcare",
          status: "active",
          summary: "Buyer needs cross-channel outreach.",
          tags: ["healthcare", "priority"],
        }),
      ),
    })
  })

  await page.goto("/customer-360")
  await page.getByRole("button", { name: "New account" }).click()
  await page.getByLabel("Name").fill("Analytical Health")
  await page.getByLabel("Website").fill("https://analytical.health")
  await page.getByLabel("Industry").fill("Healthcare")
  await page.getByLabel("Status").fill("active")
  await page.getByLabel("Summary").fill("Buyer needs cross-channel outreach.")
  await page.getByLabel("Tags").fill("healthcare, priority")
  await page.getByRole("button", { name: "Create account" }).click()

  await expect(page).toHaveURL(new RegExp(`/customer-360/${NEW_ACCOUNT_ID}$`))
  expect(createPayload).toEqual({
    name: "Analytical Health",
    website_url: "https://analytical.health",
    industry: "Healthcare",
    status: "active",
    summary: "Buyer needs cross-channel outreach.",
    tags: ["healthcare", "priority"],
  })
})

test("edits an account profile and reloads updated metadata", async ({
  page,
}) => {
  let patchPayload: Record<string, unknown> | undefined
  let profileLoadCount = 0
  const updatedProfile = accountProfile({
    account: {
      industry: "Healthcare Analytics",
      tags: ["analytics", "priority"],
      updated_at: "2026-06-08T13:00:00Z",
    },
  })

  await page.route(
    `**/api/v1/customer-360/accounts/${ACCOUNT_ID}`,
    async (route) => {
      profileLoadCount += 1
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          profileLoadCount > 1 ? updatedProfile : accountProfile(),
        ),
      })
    },
  )

  await page.route(`**/api/v1/accounts/${ACCOUNT_ID}`, async (route) => {
    expect(route.request().method()).toBe("PATCH")
    patchPayload = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(updatedProfile.account),
    })
  })

  await page.goto(`/customer-360/${ACCOUNT_ID}`)
  await page.getByRole("button", { name: "Edit account" }).click()
  await page.getByLabel("Industry").fill("Healthcare Analytics")
  await page.getByLabel("Tags").fill("analytics, priority")
  await page.getByRole("button", { name: "Save changes" }).click()

  await expect(page.getByText("Healthcare Analytics")).toBeVisible()
  await expect(
    page.locator("[data-slot='badge']").filter({ hasText: /^analytics$/ }),
  ).toBeVisible()
  await expect(
    page.locator("[data-slot='badge']").filter({ hasText: /^priority$/ }),
  ).toBeVisible()
  expect(profileLoadCount).toBeGreaterThanOrEqual(2)
  expect(patchPayload).toMatchObject({
    name: "Analytical Health",
    website_url: null,
    industry: "Healthcare Analytics",
    status: "active",
    summary: "Multi-location healthcare buyer.",
    tags: ["analytics", "priority"],
  })
})

test("assigns an available contact to an account profile", async ({ page }) => {
  let profileLoadCount = 0
  let assignPayload: Record<string, unknown> | undefined
  let assigned = false
  const assignedProfile = accountProfile({
    contacts: [
      ...accountProfile().contacts,
      {
        ...contactResponse({ account_id: ACCOUNT_ID }),
        display_name: "Alan Turing",
      },
    ],
  })

  await page.route(
    `**/api/v1/customer-360/accounts/${ACCOUNT_ID}`,
    async (route) => {
      profileLoadCount += 1
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(assigned ? assignedProfile : accountProfile()),
      })
    },
  )

  await page.route("**/api/v1/contacts/**", async (route) => {
    const url = new URL(route.request().url())
    expect(route.request().method()).toBe("GET")
    expect(url.searchParams.get("limit")).toBe("50")
    expect(url.searchParams.get("search")).toBe("Alan")
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          contactResponse(),
          contactResponse({
            id: "55555555-5555-4555-8555-555555555555",
            account_id: ACME_ACCOUNT_ID,
            email: "linked@analytical.health",
            first_name: "Linked",
            last_name: "Contact",
          }),
        ],
        count: 2,
      }),
    })
  })

  await page.route(
    `**/api/v1/accounts/${ACCOUNT_ID}/contacts`,
    async (route) => {
      expect(route.request().method()).toBe("POST")
      assignPayload = route.request().postDataJSON() as Record<string, unknown>
      assigned = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          account_id: ACCOUNT_ID,
          assigned_count: 1,
          unassigned_count: 0,
          contact_ids: [TURING_CONTACT_ID],
        }),
      })
    },
  )

  await page.goto(`/customer-360/${ACCOUNT_ID}`)
  await page.getByRole("button", { name: "Assign contacts" }).click()
  await expect(
    page.getByRole("button", { name: "Assign selected" }),
  ).toBeDisabled()
  await expect(
    page.getByText("Search contacts to find people available for this account."),
  ).toBeVisible()

  await page.getByLabel("Search contacts").fill("Alan")
  await page.getByRole("button", { name: "Search contacts" }).click()
  await expect(page.getByText("Linked Contact")).not.toBeVisible()
  await page.getByLabel("Select Alan Turing").click()

  await expect(page.getByText("1 selected")).toBeVisible()
  await page.getByRole("button", { name: "Assign selected" }).click()

  await expect(page.getByText("Alan Turing", { exact: true })).toBeVisible()
  expect(profileLoadCount).toBeGreaterThanOrEqual(2)
  expect(assignPayload).toEqual({ contact_ids: [TURING_CONTACT_ID] })
})

test("unlinks an existing contact from an account profile", async ({
  page,
}) => {
  let profileLoadCount = 0
  let unlinked = false

  await page.route(
    `**/api/v1/customer-360/accounts/${ACCOUNT_ID}`,
    async (route) => {
      profileLoadCount += 1
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          unlinked
            ? accountProfile({
                contacts: accountProfile().contacts.filter(
                  (contact) => contact.id !== "contact-ada",
                ),
              })
            : accountProfile(),
        ),
      })
    },
  )

  await page.route(
    `**/api/v1/accounts/${ACCOUNT_ID}/contacts/contact-ada`,
    async (route) => {
      expect(route.request().method()).toBe("DELETE")
      unlinked = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          account_id: ACCOUNT_ID,
          assigned_count: 0,
          unassigned_count: 1,
          contact_ids: ["contact-ada"],
        }),
      })
    },
  )

  await page.goto(`/customer-360/${ACCOUNT_ID}`)
  await expect(
    page.getByRole("button", { name: "Unlink Ada Lovelace" }),
  ).toBeVisible()

  await page.getByRole("button", { name: "Unlink Ada Lovelace" }).click()

  await expect(
    page.getByRole("button", { name: "Unlink Ada Lovelace" }),
  ).not.toBeVisible()
  await expect(page.getByText("Grace Hopper", { exact: true })).toBeVisible()
  expect(profileLoadCount).toBeGreaterThanOrEqual(2)
})

test("shows duplicate account errors for create and edit", async ({ page }) => {
  await page.route("**/api/v1/customer-360/accounts**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname.endsWith(`/customer-360/accounts/${ACCOUNT_ID}`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(accountProfile()),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(accountsResponse(accountRow())),
    })
  })

  await page.route("**/api/v1/accounts", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Account already exists" }),
    })
  })

  await page.route(`**/api/v1/accounts/${ACCOUNT_ID}`, async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Account already exists" }),
    })
  })

  await page.goto("/customer-360")
  await page.getByRole("button", { name: "New account" }).click()
  await page.getByLabel("Name").fill("Analytical Health")
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(page.getByText("Account already exists")).toBeVisible()

  await page.goto(`/customer-360/${ACCOUNT_ID}`)
  await page.getByRole("button", { name: "Edit account" }).click()
  await page.getByLabel("Name").fill("Analytical Health")
  await page.getByRole("button", { name: "Save changes" }).click()
  await expect(page.getByText("Account already exists")).toBeVisible()
})
