import { expect, test } from "@playwright/test"

const contactsPayload = {
  data: [
    {
      id: "contact-1",
      email: "ada@example.com",
      first_name: "Ada",
      last_name: "Lovelace",
      company: "Analytical",
      phone: "+15551234567",
      timezone: "America/New_York",
    },
    {
      id: "contact-2",
      email: "grace@example.com",
      first_name: "Grace",
      last_name: "Hopper",
      company: "Compiler Co",
      phone: null,
      timezone: "UTC",
    },
  ],
  count: 2,
}

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "e2e-test-token")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "owner@example.com",
        full_name: "Campaign Owner",
        is_superuser: true,
      }),
    })
  })

  await page.route(/.*\/api\/v1\/contacts\/.*/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(contactsPayload),
    })
  })
})

test("Campaigns page opens on the campaign list", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [{ id: "camp-1", name: "Q2 Outreach", status: "draft" }],
        count: 1,
      }),
    })
  })

  await page.goto("/campaigns")

  await expect(page.getByRole("heading", { name: "Campaigns" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Campaign List" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Create Campaign" })).toBeVisible()
  await expect(page.getByText("Q2 Outreach")).toBeVisible()
})

test("Campaign wizard assigns selected contacts from the lead pool", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [{ id: "camp-1", name: "Q2 Outreach", status: "draft" }],
          count: 1,
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "camp-1", name: "Q2 Outreach", status: "draft" }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-1/audience", async (route) => {
    const request = route.request()
    expect(request.postDataJSON()).toMatchObject({
      include_all_contacts: false,
      contact_ids: ["contact-1"],
      rules: [],
    })
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        campaign_id: "camp-1",
        selected_count: 1,
        added_count: 1,
        existing_count: 0,
        segment_id: "segment-1",
        segment_name: "Campaign audience",
      }),
    })
  })

  await page.goto("/campaigns")

  await page.getByRole("tab", { name: "Create Campaign" }).click()
  await page.getByLabel("Campaign name").fill("Q2 Outreach")
  await page.getByRole("button", { name: "Continue" }).click()

  await expect(page.getByText("Step 2: Audience selection")).toBeVisible()
  await page.getByLabel("Selected contacts").check()
  await page.getByRole("checkbox").first().click()
  await page.getByRole("button", { name: "Continue" }).click()

  await expect(page.getByText("1 contacts assigned to this campaign")).toBeVisible()
})

test("Campaign wizard can complete with a filtered subset", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [{ id: "camp-2", name: "Launch Wave", status: "draft" }],
          count: 1,
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "camp-2", name: "Launch Wave", status: "draft" }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-2/audience", async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({
      include_all_contacts: false,
      contact_ids: [],
      segment_name: "Enterprise subset",
      rules: [{ field_name: "company", operator: "contains", value: "Compiler" }],
    })
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        campaign_id: "camp-2",
        selected_count: 1,
        added_count: 1,
        existing_count: 0,
        segment_id: "segment-2",
        segment_name: "Enterprise subset",
      }),
    })
  })

  await page.route("**/api/v1/offer-packs/assignable", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "op-1",
            name: "Starter Pack",
            current_version: {
              id: "opv-1",
              version_number: 1,
              status: "published",
              is_default: true,
              guardrail_compliant: true,
            },
          },
        ],
        count: 1,
      }),
    })
  })

  await page.route("**/api/v1/campaigns/camp-2/strategy", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })

  await page.goto("/campaigns")

  await page.getByRole("tab", { name: "Create Campaign" }).click()
  await page.getByLabel("Campaign name").fill("Launch Wave")
  await page.getByRole("button", { name: "Continue" }).click()

  await page.getByLabel("Filtered subset").check()
  await page.getByLabel("Subset name").fill("Enterprise subset")
  await page.getByLabel("Value").fill("Compiler")
  await page.getByRole("button", { name: "Continue" }).click()

  await page.getByRole("button", { name: "Save strategy" }).click()
  await expect(page.getByRole("alert")).toContainText("Campaign intake flow complete. Draft audience and strategy saved.")
})
