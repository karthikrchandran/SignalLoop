# Outreach Hub Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Option A cleanup so Outreach keeps its current routes but gets clearer wording, contacts tabs, lead groups, campaign list-first behavior, scalable templates, clearer sequences, simplified controls, and fixed Messaging Hub analytics states.

**Architecture:** Keep changes inside the existing React/Vite/TanStack Router frontend. Prefer focused page-level helpers over new global abstractions, and reuse the existing `Tabs`, `Table`, `Pagination`, `Card`, `Badge`, and Playwright patterns already present in `apps/web`.

**Tech Stack:** React 19, Vite, TypeScript, TanStack Router, Radix UI wrappers, lucide-react, Recharts, Playwright.

---

## Scope Check

The approved spec spans several screens, but it is one cohesive operator-console cleanup in the same frontend app. Implement it as separate commits per screen so any route can be validated independently. Do not rewrite the app shell, do not replace the main Outreach Analytics page, and do not add fake metrics.

## File Map

- Modify: `apps/web/src/components/Sidebar/AppSidebar.tsx`
  - Rename the sidebar item from `Prospecting` to `Lead Preparation`.
- Modify: `apps/web/src/routes/_layout/prospecting.tsx`
  - Keep the existing `/prospecting` route but change metadata to `Lead Preparation - SignalLoop`.
- Modify: `apps/web/src/features/prospecting/ProspectingPage.tsx`
  - Rename UI copy and actions while preserving current API calls.
- Modify: `apps/web/tests/prospecting.spec.ts`
  - Update route assertions and add no-jargon checks.
- Create: `apps/web/src/features/contacts/leadGroups.ts`
  - Define client-side lead group types and matching helpers based on available contact fields.
- Modify: `apps/web/src/routes/_layout/contacts.tsx`
  - Add `leadGroupId` to search params and route to a Lead Group detail screen.
- Modify: `apps/web/src/features/contacts/ContactManagementPage.tsx`
  - Convert the page to tabs: Contacts, Lead Groups, Import.
  - Add pagination and filters to the Contacts tab.
  - Add Lead Groups list and detail link behavior.
- Create: `apps/web/tests/contacts-management.spec.ts`
  - Cover Contacts tabs, filters, pagination, and Lead Group detail navigation.
- Create: `apps/web/src/features/campaigns/CampaignsWorkspacePage.tsx`
  - Show Campaign List by default and embed the current intake wizard under Create Campaign.
- Modify: `apps/web/src/routes/_layout/campaigns.tsx`
  - Render `CampaignsWorkspacePage`.
- Modify: `apps/web/tests/campaigns.spec.ts`
  - Update existing tests to open the Create Campaign tab before wizard steps and add Campaign List assertions.
- Modify: `apps/web/src/features/templates/TemplateLibraryPage.tsx`
  - Add filters, pagination, and selected-template preview behavior.
- Modify: `apps/web/tests/templates.spec.ts`
  - Cover search/filter/pagination and preserve token preview coverage.
- Modify: `apps/web/src/features/sequences/SequencesPage.tsx`
  - Add tabs for Sequence List, Builder, Enrollments, and Performance while preserving existing create/edit/enroll behavior.
- Modify: `apps/web/tests/sequences.spec.ts`
  - Add tab assertions and adjust selectors if needed.
- Modify: `apps/web/src/features/policies/GovernanceControlPage.tsx`
  - Put pause/resume first and collapse unsupported policy copy.
- Create: `apps/web/tests/controls.spec.ts`
  - Cover pause/resume and compact unsupported-policy messaging.
- Modify: `apps/web/src/features/chatbot/AnalyticsPage.tsx`
  - Harden Messaging Hub analytics loading, error, no-data, date range, and chart states.
- Modify: `apps/web/tests/chatbot.spec.ts`
  - Add focused Messaging Hub Analytics tests for no-data and error behavior.
- Modify: `apps/web/src/routes/_layout/index.tsx`
  - Ensure dashboard Campaigns and Customer 360 links land on useful working screens.
- Modify: `apps/web/tests/dashboard-shell.spec.ts`
  - Assert dashboard links navigate correctly.
- Generated if route changes occur: `apps/web/src/routeTree.gen.ts`
  - Do not hand-edit unless TanStack route generation updates it.

---

### Task 1: Rename Prospecting to Lead Preparation

**Files:**
- Modify: `apps/web/src/components/Sidebar/AppSidebar.tsx`
- Modify: `apps/web/src/routes/_layout/prospecting.tsx`
- Modify: `apps/web/src/features/prospecting/ProspectingPage.tsx`
- Modify: `apps/web/tests/prospecting.spec.ts`

- [ ] **Step 1: Update the failing route wording test**

In `apps/web/tests/prospecting.spec.ts`, change the first test's route assertions from prospecting wording to lead-preparation wording:

```ts
await page.goto("/prospecting")

await expect(page.getByRole("heading", { name: "Lead Preparation" })).toBeVisible()
await expect(page.getByText("Leads needing follow-up")).toBeVisible()
await expect(page.getByRole("button", { name: "Build lead brief" })).toBeVisible()
await expect(page.getByText("Handoff queue")).toHaveCount(0)
await expect(page.getByRole("button", { name: "Run research" })).toHaveCount(0)
```

In the bulk test, replace the action labels:

```ts
await page.getByRole("button", { name: "Build briefs for selected" }).click()
await page.getByRole("button", { name: "Add selected to outreach" }).click()
```

- [ ] **Step 2: Run the prospecting spec and verify it fails**

Run:

```powershell
npx playwright test apps/web/tests/prospecting.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because the page still renders `Prospecting`, `Handoff queue`, and `Run research`.

- [ ] **Step 3: Implement sidebar and route metadata rename**

In `apps/web/src/components/Sidebar/AppSidebar.tsx`, change only this item:

```ts
{ icon: SearchCheck, title: "Lead Preparation", path: "/prospecting" },
```

In `apps/web/src/routes/_layout/prospecting.tsx`, update metadata:

```ts
export const Route = createFileRoute("/_layout/prospecting")({
  head: () => ({
    meta: [{ title: "Lead Preparation - SignalLoop" }],
  }),
  component: ProspectingPage,
})
```

- [ ] **Step 4: Implement Lead Preparation page copy**

In `apps/web/src/features/prospecting/ProspectingPage.tsx`, make these exact visible-copy replacements while keeping function names and API calls intact:

```tsx
<div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
  <SearchCheck className="size-4" />
  Outreach prep
</div>
<h1 className="text-3xl font-semibold tracking-tight">Lead Preparation</h1>
<p className="text-sm text-muted-foreground">
  Select leads, build lead briefs, and add prepared contacts to campaigns or sequences.
</p>
```

Replace the left card header:

```tsx
<CardTitle>Leads needing follow-up</CardTitle>
<CardDescription>
  Prioritized by buyer intent, contactability, Messaging Hub source, and account context.
</CardDescription>
```

Replace the queue label:

```tsx
<span className="font-medium">Leads needing follow-up</span>
```

Replace button labels:

```tsx
Build lead brief
Build briefs for selected
Add selected to outreach
```

Replace the main result header:

```tsx
<CardTitle>Lead brief</CardTitle>
<CardDescription>
  {result ? `Brief created ${new Date(result.created_at).toLocaleString()}` : "Build a brief for the selected lead."}
</CardDescription>
```

Replace empty state:

```tsx
Select a lead and build a brief.
```

Keep `Messaging Hub` as a source badge when `contact.handoff_source` exists.

- [ ] **Step 5: Run the prospecting spec and verify it passes**

Run:

```powershell
npx playwright test apps/web/tests/prospecting.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```powershell
git add apps/web/src/components/Sidebar/AppSidebar.tsx apps/web/src/routes/_layout/prospecting.tsx apps/web/src/features/prospecting/ProspectingPage.tsx apps/web/tests/prospecting.spec.ts
git commit -m "feat: rename prospecting to lead preparation"
```

---

### Task 2: Add Contacts Tabs, Pagination, Filters, and Lead Groups

**Files:**
- Create: `apps/web/src/features/contacts/leadGroups.ts`
- Modify: `apps/web/src/routes/_layout/contacts.tsx`
- Modify: `apps/web/src/features/contacts/ContactManagementPage.tsx`
- Create: `apps/web/tests/contacts-management.spec.ts`

- [ ] **Step 1: Write the Contacts workspace failing tests**

Create `apps/web/tests/contacts-management.spec.ts`:

```ts
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
      industry: "Financial Services",
      title: "VP Operations",
      product_interest: "Voice AI",
      source: "Messaging Hub",
      created_at: "2026-06-08T10:00:00Z",
    },
    {
      id: "contact-2",
      email: "grace@example.com",
      first_name: "Grace",
      last_name: "Hopper",
      company: "Compiler Co",
      phone: null,
      timezone: "UTC",
      industry: "Software",
      title: "CTO",
      product_interest: "Email Automation",
      source: "CSV Import",
      created_at: "2026-06-08T10:00:00Z",
    },
  ],
  count: 2,
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
        email: "owner@example.com",
        full_name: "Contacts Owner",
        is_superuser: true,
      }),
    })
  })

  await page.route("**/api/v1/contacts/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(contactsPayload),
    })
  })
})

test("Contacts page separates contacts, lead groups, and import", async ({ page }) => {
  await page.goto("/contacts")

  await expect(page.getByRole("heading", { name: "Contacts" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Contacts" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Lead Groups" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Import" })).toBeVisible()
  await expect(page.getByText("ada@example.com")).toBeVisible()
  await expect(page.getByLabel("Industry")).toBeVisible()
  await expect(page.getByLabel("Product interest")).toBeVisible()
  await expect(page.getByRole("navigation", { name: "pagination" })).toBeVisible()

  await page.getByLabel("Industry").selectOption("Software")
  await expect(page.getByText("grace@example.com")).toBeVisible()
  await expect(page.getByText("ada@example.com")).toHaveCount(0)

  await page.getByRole("tab", { name: "Import" }).click()
  await expect(page.getByText("CSV file")).toBeVisible()
  await expect(page.getByRole("button", { name: "Analyze" })).toBeVisible()
})

test("Lead Groups opens a detail screen with matching leads", async ({ page }) => {
  await page.goto("/contacts")
  await page.getByRole("tab", { name: "Lead Groups" }).click()

  await expect(page.getByRole("heading", { name: "Lead Groups" })).toBeVisible()
  await page.getByRole("link", { name: /Financial Services leaders/i }).click()

  await expect(page).toHaveURL(/leadGroupId=financial-services-leaders/)
  await expect(page.getByRole("heading", { name: "Financial Services leaders" })).toBeVisible()
  await expect(page.getByText("ada@example.com")).toBeVisible()
  await expect(page.getByText("Industry contains Financial Services")).toBeVisible()
})
```

- [ ] **Step 2: Run the Contacts test and verify it fails**

Run:

```powershell
npx playwright test apps/web/tests/contacts-management.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because tabs, filters, pagination, and lead group detail do not exist.

- [ ] **Step 3: Create Lead Group helper**

Create `apps/web/src/features/contacts/leadGroups.ts`:

```ts
export type LeadGroupField =
  | "company"
  | "industry"
  | "title"
  | "product_interest"
  | "source"
  | "phone"

export type LeadGroupOperator = "contains" | "exists"

export type LeadGroupCriterion = {
  field: LeadGroupField
  operator: LeadGroupOperator
  value?: string
}

export type LeadGroup = {
  id: string
  name: string
  description: string
  criteria: LeadGroupCriterion[]
}

export type LeadGroupContact = {
  id: string
  email: string
  company: string | null
  phone: string | null
  industry?: string | null
  title?: string | null
  product_interest?: string | null
  source?: string | null
}

export const leadGroups: LeadGroup[] = [
  {
    id: "financial-services-leaders",
    name: "Financial Services leaders",
    description: "Leads in financial services with leadership or operations roles.",
    criteria: [
      { field: "industry", operator: "contains", value: "Financial Services" },
      { field: "title", operator: "contains", value: "VP" },
    ],
  },
  {
    id: "voice-ready-leads",
    name: "Voice-ready leads",
    description: "Contacts with phone numbers available for voice outreach.",
    criteria: [{ field: "phone", operator: "exists" }],
  },
  {
    id: "messaging-hub-leads",
    name: "Messaging Hub leads",
    description: "Contacts sourced from Messaging Hub conversations.",
    criteria: [{ field: "source", operator: "contains", value: "Messaging Hub" }],
  },
]

export function criterionLabel(criterion: LeadGroupCriterion) {
  if (criterion.operator === "exists") {
    return `${criterion.field.replace(/_/g, " ")} exists`
  }
  return `${criterion.field.replace(/_/g, " ")} contains ${criterion.value}`
}

export function matchesLeadGroup(contact: LeadGroupContact, group: LeadGroup) {
  return group.criteria.every((criterion) => {
    const rawValue = contact[criterion.field]
    if (criterion.operator === "exists") {
      return Boolean(String(rawValue || "").trim())
    }
    return String(rawValue || "")
      .toLowerCase()
      .includes(String(criterion.value || "").toLowerCase())
  })
}
```

- [ ] **Step 4: Extend the contacts route search schema**

In `apps/web/src/routes/_layout/contacts.tsx`, add `leadGroupId`:

```ts
const contactsSearchSchema = z.object({
  contactId: z.string().optional(),
  campaignId: z.string().optional(),
  contactName: z.string().optional(),
  leadGroupId: z.string().optional(),
})
```

Update `ContactsPage`:

```tsx
function ContactsPage() {
  const { contactId, campaignId, contactName, leadGroupId } = Route.useSearch()

  if (contactId) {
    return (
      <ContactTimelinePage
        contactId={contactId}
        campaignId={campaignId}
        contactName={contactName}
      />
    )
  }

  return <ContactManagementPage leadGroupId={leadGroupId} />
}
```

- [ ] **Step 5: Add optional fields and props in ContactManagementPage**

In `apps/web/src/features/contacts/ContactManagementPage.tsx`, extend `Contact`:

```ts
type Contact = {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  company: string | null
  phone: string | null
  timezone: string
  created_at: string
  industry?: string | null
  title?: string | null
  product_interest?: string | null
  source?: string | null
}
```

Change the component signature:

```tsx
type ContactManagementPageProps = {
  leadGroupId?: string
}

export default function ContactManagementPage({ leadGroupId }: ContactManagementPageProps) {
```

- [ ] **Step 6: Implement tabs, filters, pagination, and detail behavior**

Use the existing imports plus these additions:

```tsx
import { Link } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import {
  criterionLabel,
  leadGroups,
  matchesLeadGroup,
} from "@/features/contacts/leadGroups"
```

Add state:

```tsx
const [industryFilter, setIndustryFilter] = useState("all")
const [titleFilter, setTitleFilter] = useState("all")
const [interestFilter, setInterestFilter] = useState("all")
const [sourceFilter, setSourceFilter] = useState("all")
const [page, setPage] = useState(1)
const [pageSize] = useState(10)
```

Add derived collections:

```tsx
const uniqueValues = (field: keyof Contact) =>
  Array.from(new Set(contacts.map((contact) => contact[field]).filter(Boolean).map(String))).sort()

const filteredContacts = contacts.filter((contact) => {
  if (industryFilter !== "all" && contact.industry !== industryFilter) return false
  if (titleFilter !== "all" && contact.title !== titleFilter) return false
  if (interestFilter !== "all" && contact.product_interest !== interestFilter) return false
  if (sourceFilter !== "all" && contact.source !== sourceFilter) return false
  return true
})

const pageCount = Math.max(1, Math.ceil(filteredContacts.length / pageSize))
const pagedContacts = filteredContacts.slice((page - 1) * pageSize, page * pageSize)
const selectedLeadGroup = leadGroups.find((group) => group.id === leadGroupId)
const selectedLeadGroupContacts = selectedLeadGroup
  ? contacts.filter((contact) => matchesLeadGroup(contact, selectedLeadGroup))
  : []
```

If `selectedLeadGroup` exists, render a detail screen before the normal tabbed workspace:

```tsx
if (selectedLeadGroup) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button asChild variant="outline">
          <Link to="/contacts">Back to Contacts</Link>
        </Button>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">{selectedLeadGroup.name}</h1>
        <p className="text-sm text-muted-foreground">{selectedLeadGroup.description}</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Group criteria</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {selectedLeadGroup.criteria.map((criterion) => (
            <Badge key={`${criterion.field}-${criterion.operator}-${criterion.value || "exists"}`} variant="outline">
              {criterionLabel(criterion)}
            </Badge>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Matching leads</CardTitle>
          <CardDescription>{selectedLeadGroupContacts.length} matching lead(s)</CardDescription>
        </CardHeader>
        <CardContent>
          <ContactTable contacts={selectedLeadGroupContacts} />
        </CardContent>
      </Card>
    </div>
  )
}
```

Refactor the contacts table into a local `ContactTable` function at the bottom of the file:

```tsx
function ContactTable({ contacts }: { contacts: Contact[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Email</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Company</TableHead>
          <TableHead>Title</TableHead>
          <TableHead>Product interest</TableHead>
          <TableHead>Phone</TableHead>
          <TableHead>Timezone</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {contacts.length === 0 ? (
          <TableRow>
            <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
              No contacts found.
            </TableCell>
          </TableRow>
        ) : (
          contacts.map((contact) => (
            <TableRow key={contact.id}>
              <TableCell className="font-medium">{contact.email}</TableCell>
              <TableCell>{contactName(contact)}</TableCell>
              <TableCell>{contact.company || "-"}</TableCell>
              <TableCell>{contact.title || "-"}</TableCell>
              <TableCell>{contact.product_interest || "-"}</TableCell>
              <TableCell>{contact.phone || "-"}</TableCell>
              <TableCell>{contact.timezone || "UTC"}</TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
```

Wrap the normal content in:

```tsx
<Tabs defaultValue="contacts" className="gap-6">
  <TabsList className="flex h-auto flex-wrap">
    <TabsTrigger value="contacts">Contacts</TabsTrigger>
    <TabsTrigger value="lead-groups">Lead Groups</TabsTrigger>
    <TabsTrigger value="import">Import</TabsTrigger>
  </TabsList>
  <TabsContent value="contacts" className="space-y-4">
    {/* search, filters, paged ContactTable, pagination */}
  </TabsContent>
  <TabsContent value="lead-groups" className="space-y-4">
    {/* lead group cards */}
  </TabsContent>
  <TabsContent value="import" className="space-y-6">
    {/* existing import, mapping, preview, validation content */}
  </TabsContent>
</Tabs>
```

Render Lead Group cards with route search:

```tsx
{leadGroups.map((group) => {
  const matchCount = contacts.filter((contact) => matchesLeadGroup(contact, group)).length
  return (
    <Card key={group.id}>
      <CardHeader>
        <CardTitle>{group.name}</CardTitle>
        <CardDescription>{group.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {group.criteria.map((criterion) => (
            <Badge key={`${group.id}-${criterion.field}-${criterion.value || criterion.operator}`} variant="outline">
              {criterionLabel(criterion)}
            </Badge>
          ))}
        </div>
        <Button asChild variant="outline">
          <Link to="/contacts" search={{ leadGroupId: group.id }}>
            Open group ({matchCount})
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
})}
```

Render pagination:

```tsx
<Pagination>
  <PaginationContent>
    <PaginationItem>
      <PaginationPrevious
        href="#"
        onClick={(event) => {
          event.preventDefault()
          setPage((current) => Math.max(1, current - 1))
        }}
        aria-disabled={page === 1}
      />
    </PaginationItem>
    <PaginationItem>
      <span className="px-3 text-sm text-muted-foreground">
        Page {page} of {pageCount}
      </span>
    </PaginationItem>
    <PaginationItem>
      <PaginationNext
        href="#"
        onClick={(event) => {
          event.preventDefault()
          setPage((current) => Math.min(pageCount, current + 1))
        }}
        aria-disabled={page === pageCount}
      />
    </PaginationItem>
  </PaginationContent>
</Pagination>
```

- [ ] **Step 7: Run the Contacts test and verify it passes**

Run:

```powershell
npx playwright test apps/web/tests/contacts-management.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```powershell
git add apps/web/src/features/contacts/leadGroups.ts apps/web/src/routes/_layout/contacts.tsx apps/web/src/features/contacts/ContactManagementPage.tsx apps/web/tests/contacts-management.spec.ts
git commit -m "feat: add contacts workspace tabs and lead groups"
```

---

### Task 3: Make Campaigns List-First

**Files:**
- Create: `apps/web/src/features/campaigns/CampaignsWorkspacePage.tsx`
- Modify: `apps/web/src/routes/_layout/campaigns.tsx`
- Modify: `apps/web/tests/campaigns.spec.ts`

- [ ] **Step 1: Update Campaigns tests**

In `apps/web/tests/campaigns.spec.ts`, add this test before the wizard tests:

```ts
test("Campaigns opens to a campaign list before intake", async ({ page }) => {
  await page.route("**/api/v1/campaigns/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          { id: "camp-1", name: "Q2 Outreach", status: "draft" },
          { id: "camp-2", name: "Launch Wave", status: "active" },
        ],
        count: 2,
      }),
    })
  })

  await page.goto("/campaigns")

  await expect(page.getByRole("heading", { name: "Campaigns" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Campaign List" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Create Campaign" })).toBeVisible()
  await expect(page.getByText("Q2 Outreach")).toBeVisible()
  await expect(page.getByText("Launch Wave")).toBeVisible()
})
```

In both existing wizard tests, after `await page.goto("/campaigns")`, add:

```ts
await page.getByRole("tab", { name: "Create Campaign" }).click()
```

- [ ] **Step 2: Run Campaigns tests and verify failure**

Run:

```powershell
npx playwright test apps/web/tests/campaigns.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because Campaign List does not exist.

- [ ] **Step 3: Create CampaignsWorkspacePage**

Create `apps/web/src/features/campaigns/CampaignsWorkspacePage.tsx`:

```tsx
import { useEffect, useState } from "react"
import { Loader2, RefreshCw } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { signalloopRequest } from "@/lib/signalloop-api"
import CampaignIntakeWizardPage from "./CampaignIntakeWizardPage"

type CampaignSummary = {
  id: string
  name: string
  status: string
  created_at?: string | null
  audience_count?: number | null
  sequence_name?: string | null
}

type CampaignsResponse = {
  data: CampaignSummary[]
  count?: number
}

export default function CampaignsWorkspacePage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  async function loadCampaigns() {
    setLoading(true)
    setError("")
    try {
      const response = await signalloopRequest<CampaignsResponse>("/api/v1/campaigns/")
      setCampaigns(response.data || [])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load campaigns")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCampaigns()
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Campaigns</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Review existing campaigns or create a new campaign from the intake flow.
        </p>
      </div>

      <Tabs defaultValue="list" className="gap-6">
        <TabsList className="flex h-auto flex-wrap">
          <TabsTrigger value="list">Campaign List</TabsTrigger>
          <TabsTrigger value="create">Create Campaign</TabsTrigger>
        </TabsList>
        <TabsContent value="list">
          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle>Campaign List</CardTitle>
                <CardDescription>Existing campaign drafts and active outreach work.</CardDescription>
              </div>
              <Button variant="outline" onClick={() => void loadCampaigns()} disabled={loading}>
                {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
                Refresh
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {error && <Alert variant="destructive">{error}</Alert>}
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  Loading campaigns...
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Campaign</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Audience</TableHead>
                      <TableHead>Sequence</TableHead>
                      <TableHead>Next action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {campaigns.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                          No campaigns found. Use Create Campaign to start a draft.
                        </TableCell>
                      </TableRow>
                    ) : (
                      campaigns.map((campaign) => (
                        <TableRow key={campaign.id}>
                          <TableCell className="font-medium">{campaign.name}</TableCell>
                          <TableCell><Badge variant="outline">{campaign.status}</Badge></TableCell>
                          <TableCell>{campaign.audience_count ?? "Not assigned"}</TableCell>
                          <TableCell>{campaign.sequence_name || "Not assigned"}</TableCell>
                          <TableCell>{campaign.status === "draft" ? "Finish setup" : "Review performance"}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="create">
          <CampaignIntakeWizardPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

- [ ] **Step 4: Render CampaignsWorkspacePage from the route**

In `apps/web/src/routes/_layout/campaigns.tsx`, replace imports and component:

```tsx
import { createFileRoute } from "@tanstack/react-router"

import CampaignsWorkspacePage from "@/features/campaigns/CampaignsWorkspacePage"

export const Route = createFileRoute("/_layout/campaigns")({
  component: CampaignsWorkspacePage,
  head: () => ({
    meta: [
      {
        title: "Campaigns - SignalLoop",
      },
    ],
  }),
})
```

- [ ] **Step 5: Run Campaigns tests**

Run:

```powershell
npx playwright test apps/web/tests/campaigns.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```powershell
git add apps/web/src/features/campaigns/CampaignsWorkspacePage.tsx apps/web/src/routes/_layout/campaigns.tsx apps/web/tests/campaigns.spec.ts
git commit -m "feat: make campaigns list first"
```

---

### Task 4: Add Template Filters and Pagination

**Files:**
- Modify: `apps/web/src/features/templates/TemplateLibraryPage.tsx`
- Modify: `apps/web/tests/templates.spec.ts`

- [ ] **Step 1: Add failing Template Library assertions**

Append this test to `apps/web/tests/templates.spec.ts`:

```ts
test("Template library supports filtering and pagination", async ({ page }) => {
  await page.route("**/api/v1/templates/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: [
          {
            id: "tpl-1",
            name: "Welcome",
            channel: "email",
            current_version: { id: "tv-1", version_number: 1, status: "draft", guardrail_compliant: false, subject: "Hi", content: "Hello" },
          },
          {
            id: "tpl-2",
            name: "Voice Opener",
            channel: "voice",
            current_version: { id: "tv-2", version_number: 1, status: "published", guardrail_compliant: true, subject: null, content: "Opening script" },
          },
        ],
      }),
    })
  })

  await page.goto("/templates")

  await expect(page.getByLabel("Search templates")).toBeVisible()
  await expect(page.getByLabel("Channel")).toBeVisible()
  await expect(page.getByLabel("Status")).toBeVisible()
  await page.getByLabel("Channel").selectOption("voice")
  await expect(page.getByText("Voice Opener")).toBeVisible()
  await expect(page.getByText("Welcome")).toHaveCount(0)
  await expect(page.getByRole("navigation", { name: "pagination" })).toBeVisible()
})
```

- [ ] **Step 2: Run Template tests and verify failure**

Run:

```powershell
npx playwright test apps/web/tests/templates.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because filters and pagination do not exist.

- [ ] **Step 3: Add TemplateLibraryPage state and filtering**

In `TemplateLibraryPage.tsx`, add imports:

```tsx
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
```

Add state:

```tsx
const [templateSearch, setTemplateSearch] = useState("")
const [channelFilter, setChannelFilter] = useState("all")
const [statusFilter, setStatusFilter] = useState("all")
const [page, setPage] = useState(1)
const pageSize = 10
```

Add derived templates:

```tsx
const filteredTemplates = templates.filter((template) => {
  const searchText = `${template.name} ${template.current_version?.subject || ""} ${template.current_version?.content || ""}`.toLowerCase()
  if (templateSearch.trim() && !searchText.includes(templateSearch.trim().toLowerCase())) return false
  if (channelFilter !== "all" && template.channel !== channelFilter) return false
  if (statusFilter !== "all" && template.current_version?.status !== statusFilter) return false
  return true
})
const templatePageCount = Math.max(1, Math.ceil(filteredTemplates.length / pageSize))
const pagedTemplates = filteredTemplates.slice((page - 1) * pageSize, page * pageSize)
```

Render controls before `Publish Readiness`:

```tsx
<Card>
  <CardHeader>
    <CardTitle>Browse Templates</CardTitle>
    <CardDescription>Search and filter reusable content before previewing or publishing.</CardDescription>
  </CardHeader>
  <CardContent className="space-y-4">
    <div className="grid gap-3 md:grid-cols-3">
      <div className="grid gap-1.5">
        <Label htmlFor="template-search">Search templates</Label>
        <Input id="template-search" value={templateSearch} onChange={(event) => setTemplateSearch(event.target.value)} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="template-channel-filter">Channel</Label>
        <select id="template-channel-filter" className="h-10 rounded-md border bg-background px-3 text-sm" value={channelFilter} onChange={(event) => setChannelFilter(event.target.value)}>
          <option value="all">All channels</option>
          <option value="email">Email</option>
          <option value="voice">Voice</option>
          <option value="sms">SMS</option>
        </select>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="template-status-filter">Status</Label>
        <select id="template-status-filter" className="h-10 rounded-md border bg-background px-3 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
      </div>
    </div>
    <div className="space-y-2">
      {pagedTemplates.map((template) => (
        <button key={template.id} type="button" className="w-full rounded-md border p-3 text-left" onClick={() => setSelectedTemplateId(template.id)}>
          <p className="font-medium">{template.name}</p>
          <p className="text-sm text-muted-foreground">{template.channel} / {template.current_version?.status || "no version"}</p>
        </button>
      ))}
    </div>
    <Pagination>
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious href="#" onClick={(event) => { event.preventDefault(); setPage((current) => Math.max(1, current - 1)) }} />
        </PaginationItem>
        <PaginationItem><span className="px-3 text-sm text-muted-foreground">Page {page} of {templatePageCount}</span></PaginationItem>
        <PaginationItem>
          <PaginationNext href="#" onClick={(event) => { event.preventDefault(); setPage((current) => Math.min(templatePageCount, current + 1)) }} />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  </CardContent>
</Card>
```

- [ ] **Step 4: Run Template tests**

Run:

```powershell
npx playwright test apps/web/tests/templates.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```powershell
git add apps/web/src/features/templates/TemplateLibraryPage.tsx apps/web/tests/templates.spec.ts
git commit -m "feat: add template filtering and pagination"
```

---

### Task 5: Clarify Sequence Sections

**Files:**
- Modify: `apps/web/src/features/sequences/SequencesPage.tsx`
- Modify: `apps/web/tests/sequences.spec.ts`

- [ ] **Step 1: Add failing sequence tab assertions**

In `apps/web/tests/sequences.spec.ts`, in `test("Sequences page loads and shows the sequence list"...`, after the heading assertion add:

```ts
await expect(page.getByRole("tab", { name: "Sequence List" })).toBeVisible()
await expect(page.getByRole("tab", { name: "Builder" })).toBeVisible()
await expect(page.getByRole("tab", { name: "Enrollments" })).toBeVisible()
await expect(page.getByRole("tab", { name: "Performance" })).toBeVisible()
```

- [ ] **Step 2: Run Sequences tests and verify failure**

Run:

```powershell
npx playwright test apps/web/tests/sequences.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because tabs do not exist.

- [ ] **Step 3: Add Tabs around the existing sequence content**

In `apps/web/src/features/sequences/SequencesPage.tsx`, add:

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
```

Wrap the existing two-column sequence list/detail grid in:

```tsx
<Tabs defaultValue="list" className="gap-6">
  <TabsList className="flex h-auto flex-wrap">
    <TabsTrigger value="list">Sequence List</TabsTrigger>
    <TabsTrigger value="builder">Builder</TabsTrigger>
    <TabsTrigger value="enrollments">Enrollments</TabsTrigger>
    <TabsTrigger value="performance">Performance</TabsTrigger>
  </TabsList>
  <TabsContent value="list">
    {/* existing two-column sequence list/detail grid */}
  </TabsContent>
  <TabsContent value="builder">
    <Card>
      <CardHeader>
        <CardTitle>Builder</CardTitle>
        <CardDescription>Create or edit ordered outreach steps.</CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={openCreateDialog} disabled={campaigns.length === 0}>
          <Plus className="mr-2 h-4 w-4" />
          New Sequence
        </Button>
      </CardContent>
    </Card>
  </TabsContent>
  <TabsContent value="enrollments">
    <Card>
      <CardHeader>
        <CardTitle>Enrollments</CardTitle>
        <CardDescription>Current enrollment status for the selected sequence.</CardDescription>
      </CardHeader>
      <CardContent>
        {selectedProgress ? (
          <div className="flex flex-wrap gap-2">
            {Object.entries(selectedProgress.status_breakdown).map(([status, count]) => (
              <Badge key={status} variant="outline">{`${status}: ${count}`}</Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Select a sequence to inspect enrollments.</p>
        )}
      </CardContent>
    </Card>
  </TabsContent>
  <TabsContent value="performance">
    <Card>
      <CardHeader>
        <CardTitle>Performance</CardTitle>
        <CardDescription>Delivery and response metrics appear here when connected.</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">No sequence performance data is available for this build.</p>
      </CardContent>
    </Card>
  </TabsContent>
</Tabs>
```

Keep the existing dialog outside the tabs so create/edit still works.

- [ ] **Step 4: Run Sequences tests**

Run:

```powershell
npx playwright test apps/web/tests/sequences.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```powershell
git add apps/web/src/features/sequences/SequencesPage.tsx apps/web/tests/sequences.spec.ts
git commit -m "feat: clarify sequence workspace sections"
```

---

### Task 6: Simplify Controls

**Files:**
- Modify: `apps/web/src/features/policies/GovernanceControlPage.tsx`
- Create: `apps/web/tests/controls.spec.ts`

- [ ] **Step 1: Write failing Controls test**

Create `apps/web/tests/controls.spec.ts`:

```ts
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

test("Controls focuses on pause and resume", async ({ page }) => {
  await page.route("**/api/v1/controls/pause", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })
  await page.route("**/api/v1/controls/resume", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  })

  await page.goto("/controls")

  await expect(page.getByRole("heading", { name: "Outreach Controls" })).toBeVisible()
  await expect(page.getByText("Emergency pause")).toBeVisible()
  await expect(page.getByText("Daily sending limits")).toHaveCount(0)

  await page.getByLabel("Reason for pausing").fill("Compliance review")
  await page.getByRole("button", { name: "Pause all outreach" }).click()
  await expect(page.getByText("All outreach has been paused")).toBeVisible()
  await page.getByRole("button", { name: "Resume outreach" }).click()
  await expect(page.getByText("Outreach has been resumed")).toBeVisible()
})
```

- [ ] **Step 2: Run Controls test and verify failure**

Run:

```powershell
npx playwright test apps/web/tests/controls.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because the current page still leads with daily limits and quiet hours.

- [ ] **Step 3: Move emergency controls first and remove bloated unsupported cards**

In `GovernanceControlPage.tsx`, change the page description:

```tsx
<p className="max-w-3xl text-sm text-muted-foreground">
  Pause or resume outbound activity across campaigns and sequences.
</p>
```

Rename the emergency card title:

```tsx
<CardTitle>Emergency pause</CardTitle>
```

Remove the full Daily sending limits and Do not disturb hours cards from the main render. Replace them with one compact card after emergency controls:

```tsx
<Card>
  <CardHeader>
    <CardTitle>Policy settings</CardTitle>
    <CardDescription>
      Daily limits and quiet hours are enforced by backend configuration in this build.
    </CardDescription>
  </CardHeader>
  <CardContent>
    <p className="text-sm text-muted-foreground">
      Editing those policies from the UI requires a supported controls API. This page exposes only the supported pause and resume controls.
    </p>
  </CardContent>
</Card>
```

- [ ] **Step 4: Run Controls test**

Run:

```powershell
npx playwright test apps/web/tests/controls.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```powershell
git add apps/web/src/features/policies/GovernanceControlPage.tsx apps/web/tests/controls.spec.ts
git commit -m "feat: simplify outreach controls"
```

---

### Task 7: Harden Messaging Hub Analytics

**Files:**
- Modify: `apps/web/src/features/chatbot/AnalyticsPage.tsx`
- Modify: `apps/web/tests/chatbot.spec.ts`

- [ ] **Step 1: Add failing Messaging Hub Analytics tests**

Append these tests to `apps/web/tests/chatbot.spec.ts`:

```ts
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

  await expect(page.getByText("No messaging analytics for this range")).toBeVisible()
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
```

- [ ] **Step 2: Run Chatbot tests and verify failure**

Run:

```powershell
npx playwright test apps/web/tests/chatbot.spec.ts --project=chromium --reporter=line
```

Expected: FAIL because the error state has no explicit retry button and no-data copy is not consistent.

- [ ] **Step 3: Implement retryable error and explicit no-data state**

In `apps/web/src/features/chatbot/AnalyticsPage.tsx`, change the error block to:

```tsx
{error ? (
  <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <span>{error}</span>
      <Button variant="outline" onClick={() => void load()} disabled={loading}>
        Retry
      </Button>
    </div>
  </div>
) : null}
```

Add:

```tsx
const hasAnyAnalytics = Boolean(
  data &&
    (data.totals.conversations > 0 ||
      data.totals.leads_captured > 0 ||
      data.totals.escalations > 0 ||
      data.timeseries.length > 0 ||
      data.channel_breakdown.length > 0),
)
```

After metric cards and before the funnel card, render:

```tsx
{data && !hasAnyAnalytics ? (
  <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
    No messaging analytics for this range.
  </div>
) : null}
```

Keep `EmptyChart` for both charts.

- [ ] **Step 4: Run Chatbot tests**

Run:

```powershell
npx playwright test apps/web/tests/chatbot.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```powershell
git add apps/web/src/features/chatbot/AnalyticsPage.tsx apps/web/tests/chatbot.spec.ts
git commit -m "fix: harden messaging hub analytics states"
```

---

### Task 8: Verify Dashboard Links and Build

**Files:**
- Modify: `apps/web/tests/dashboard-shell.spec.ts`
- Modify if needed: `apps/web/src/routes/_layout/index.tsx`

- [ ] **Step 1: Add dashboard link assertions**

In `apps/web/tests/dashboard-shell.spec.ts`, append:

```ts
test("dashboard campaign and Customer 360 links navigate to working screens", async ({ page }) => {
  await page.goto("/")

  await page.getByRole("link", { name: /Open campaigns/i }).click()
  await expect(page).toHaveURL(/\/campaigns/)
  await expect(page.getByRole("heading", { name: "Campaigns" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Campaign List" })).toBeVisible()

  await page.goto("/")
  await page.getByRole("link", { name: /Customer 360/i }).first().click()
  await expect(page).toHaveURL(/\/customer-360/)
})
```

- [ ] **Step 2: Run dashboard shell test**

Run:

```powershell
npx playwright test apps/web/tests/dashboard-shell.spec.ts --project=chromium --reporter=line
```

Expected: PASS. If the Campaigns link does not land on Campaign List, adjust `apps/web/src/routes/_layout/index.tsx` only by changing the link target or link text. Do not add new fake dashboard metrics.

- [ ] **Step 3: Run focused route specs**

Run:

```powershell
npx playwright test apps/web/tests/prospecting.spec.ts apps/web/tests/contacts-management.spec.ts apps/web/tests/campaigns.spec.ts apps/web/tests/templates.spec.ts apps/web/tests/sequences.spec.ts apps/web/tests/controls.spec.ts apps/web/tests/chatbot.spec.ts apps/web/tests/dashboard-shell.spec.ts --project=chromium --reporter=line
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm --workspace frontend run build
```

Expected: PASS. If `apps/web/src/routeTree.gen.ts` changes due TanStack route generation, inspect it and include only generated route-tree changes that match intentional route edits.

- [ ] **Step 5: Run diff hygiene**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable if Git reports them as warnings rather than errors.

- [ ] **Step 6: Commit final verification updates**

```powershell
git add apps/web/tests/dashboard-shell.spec.ts apps/web/src/routes/_layout/index.tsx apps/web/src/routeTree.gen.ts
git commit -m "test: verify outreach hub navigation"
```

If `apps/web/src/routes/_layout/index.tsx` and `apps/web/src/routeTree.gen.ts` are unchanged, commit only `apps/web/tests/dashboard-shell.spec.ts`.

---

## Final Verification

Run:

```powershell
npx playwright test apps/web/tests/prospecting.spec.ts apps/web/tests/contacts-management.spec.ts apps/web/tests/campaigns.spec.ts apps/web/tests/templates.spec.ts apps/web/tests/sequences.spec.ts apps/web/tests/controls.spec.ts apps/web/tests/chatbot.spec.ts apps/web/tests/dashboard-shell.spec.ts --project=chromium --reporter=line
npm --workspace frontend run build
git diff --check
git status --short
```

Expected:

- All listed Playwright specs pass.
- Frontend build passes.
- `git diff --check` passes.
- `git status --short` contains only intentional changes or is clean after commits.

Do not claim completion if any command fails. Report the exact failing command and failure text.
