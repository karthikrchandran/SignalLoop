import { expect, test } from "@playwright/test"

import {
  apiBaseUrl,
  defaultWorkspaceId,
  firstSuperuser,
  firstSuperuserPassword,
} from "./config"

type AuthHeaders = {
  Authorization: string
  "X-Workspace-Id": string
}

type AuthContext = {
  accessToken: string
  headers: AuthHeaders
}

type CampaignPublic = {
  id: string
  name: string
}

type ContactPublic = {
  id: string
  email: string
}

type SequencePublic = {
  id: string
  name: string
}

async function loginForApi(request: Parameters<Parameters<typeof test>[1]>[0]["request"]) {
  const injectedAccessToken = process.env.PLAYWRIGHT_ACCESS_TOKEN
  if (injectedAccessToken) {
    return {
      accessToken: injectedAccessToken,
      headers: {
        Authorization: `Bearer ${injectedAccessToken}`,
        "X-Workspace-Id": defaultWorkspaceId,
      },
    } satisfies AuthContext
  }

  const response = await request.post(`${apiBaseUrl}/api/v1/login/access-token`, {
    form: {
      username: firstSuperuser,
      password: firstSuperuserPassword,
    },
  })

  expect(response.ok()).toBeTruthy()
  const body = (await response.json()) as { access_token: string }

  return {
    accessToken: body.access_token,
    headers: {
      Authorization: `Bearer ${body.access_token}`,
      "X-Workspace-Id": defaultWorkspaceId,
    },
  } satisfies AuthContext
}

async function createCampaign(request: Parameters<Parameters<typeof test>[1]>[0]["request"], headers: AuthHeaders, name: string) {
  const response = await request.post(`${apiBaseUrl}/api/v1/campaigns/`, {
    headers,
    data: { name },
  })

  expect(response.ok()).toBeTruthy()
  return (await response.json()) as CampaignPublic
}

async function importContact(
  request: Parameters<Parameters<typeof test>[1]>[0]["request"],
  headers: AuthHeaders,
  timestamp: string,
) {
  const email = `ui-smoke+${timestamp}@example.com`
  const csv = [
    "email,firstName,lastName,company,phone,timezone",
    `${email},UI,Smoke,EngageHub,+15555550124,UTC`,
    "",
  ].join("\n")

  const importResponse = await request.post(`${apiBaseUrl}/api/v1/contacts/import`, {
    headers,
    multipart: {
      file: {
        name: `ui-smoke-${timestamp}.csv`,
        mimeType: "text/csv",
        buffer: Buffer.from(csv, "utf-8"),
      },
      commit: "true",
    },
  })

  expect(importResponse.ok()).toBeTruthy()

  const contactsResponse = await request.get(
    `${apiBaseUrl}/api/v1/contacts/?search=${encodeURIComponent(email)}`,
    { headers },
  )
  expect(contactsResponse.ok()).toBeTruthy()
  const contactsBody = (await contactsResponse.json()) as { data: ContactPublic[] }
  expect(contactsBody.data.length).toBeGreaterThan(0)

  return contactsBody.data[0]
}

async function assignAudience(
  request: Parameters<Parameters<typeof test>[1]>[0]["request"],
  headers: AuthHeaders,
  campaignId: string,
  contactId: string,
) {
  const response = await request.post(`${apiBaseUrl}/api/v1/campaigns/${campaignId}/audience`, {
    headers,
    data: {
      include_all_contacts: false,
      contact_ids: [contactId],
      segment_name: null,
      rules: [],
    },
  })

  expect(response.ok()).toBeTruthy()
}

test.describe.configure({ mode: "serial" })
test.use({ storageState: { cookies: [], origins: [] } })

test("live corrective smoke covers Sequences and Voice Setup UI", async ({ page, request }) => {
  const timestamp = Date.now().toString()
  const auth = await loginForApi(request)
  const headers = auth.headers
  const contact = await importContact(request, headers, timestamp)
  const campaign = await createCampaign(request, headers, `UI Smoke Campaign ${timestamp}`)
  await assignAudience(request, headers, campaign.id, contact.id)

  await page.addInitScript(
    ({ accessToken, workspaceId }) => {
      localStorage.setItem("access_token", accessToken)
      localStorage.setItem("workspace_id", workspaceId)
    },
    { accessToken: auth.accessToken, workspaceId: defaultWorkspaceId },
  )

  await page.goto("/sequences")
  await expect(page.getByRole("heading", { name: "Sequences" })).toBeVisible()

  await page.getByRole("button", { name: /new sequence/i }).click()
  await page.getByLabel(/sequence name/i).fill(`UI Smoke Sequence ${timestamp}`)
  await page.getByPlaceholder("Subject line").fill(`Smoke subject ${timestamp}`)
  await page.getByPlaceholder("Email body").fill(`Hello {{first_name}}, this is UI smoke ${timestamp}.`)
  await page.getByRole("button", { name: /create sequence/i }).click()

  await expect(page.getByText(/sequence created/i)).toBeVisible()
  await expect(page.getByText(`Smoke subject ${timestamp}`)).toBeVisible()

  const enrollResponsePromise = page.waitForResponse((response) => {
    return response.url().includes("/api/v1/sequences/")
      && response.url().includes("/enroll/")
      && response.request().method() === "POST"
  })
  await page.getByRole("button", { name: /enroll contacts/i }).click()
  const enrollResponse = await enrollResponsePromise
  expect(enrollResponse.ok()).toBeTruthy()
  await expect(page.getByText(/enrolled 1 contacts/i)).toBeVisible()
  await expect(page.getByText(/active: 1/i)).toBeVisible()

  const sequenceListResponse = await request.get(`${apiBaseUrl}/api/v1/sequences/`, { headers })
  expect(sequenceListResponse.ok()).toBeTruthy()
  const sequenceList = (await sequenceListResponse.json()) as { data: SequencePublic[] }
  const createdSequence = sequenceList.data.find((sequence) => sequence.name === `UI Smoke Sequence ${timestamp}`)
  expect(createdSequence).toBeTruthy()

  const progressResponse = await request.get(`${apiBaseUrl}/api/v1/sequences/${createdSequence?.id}/progress`, { headers })
  expect(progressResponse.ok()).toBeTruthy()
  const progress = (await progressResponse.json()) as { total_enrolled: number; status_breakdown: Record<string, number> }
  expect(progress.total_enrolled).toBe(1)
  expect(progress.status_breakdown.active).toBe(1)

  await page.goto("/voice-agents")
  await expect(page.getByRole("heading", { name: "Voice Setup" })).toBeVisible()
  await expect(page.getByText("Twilio Voice")).toBeVisible()

  await page.getByRole("button", { name: /new script/i }).click()
  await page.getByLabel(/script name/i).fill(`UI Smoke Script ${timestamp}`)
  await page.getByRole("button", { name: /create script/i }).click()

  await expect(page.getByText(/script created/i)).toBeVisible()
  await expect(page.getByRole("textbox", { name: /script content/i })).toHaveValue(
    /Hi \{\{first_name\}\}, this is EngageHub calling about your campaign\./,
  )

  await page.getByRole("button", { name: /^edit$/i }).click()
  const scriptNameInput = page.getByLabel(/script name/i)
  await scriptNameInput.clear()
  await scriptNameInput.fill(`UI Smoke Script Updated ${timestamp}`)
  await page.getByRole("button", { name: /save changes/i }).click()
    await expect(page.getByText(/^Script updated\.$/)).toBeVisible()

  await page.getByRole("button", { name: /deactivate/i }).click()
  await expect(page.getByText(/script deactivated/i)).toBeVisible()
})