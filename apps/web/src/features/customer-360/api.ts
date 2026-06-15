import { signalloopRequest } from "@/lib/signalloop-api"

export type Customer360Account = {
  id: string
  workspace_id: string
  name: string
  account_key: string
  website_url?: string | null
  industry?: string | null
  status: string
  summary?: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export type Customer360AccountRow = Customer360Account & {
  contact_count: number
  last_activity_at?: string | null
  channel_counts: Record<string, number>
  top_next_action?: string | null
}

export type Customer360AccountsResponse = {
  data: Customer360AccountRow[]
  count: number
}

export type AccountWriteInput = {
  name: string
  website_url?: string | null
  industry?: string | null
  status: string
  summary?: string | null
  tags: string[]
}

export type Customer360Contact = {
  id: string
  workspace_id: string
  account_id?: string | null
  email: string
  first_name?: string | null
  last_name?: string | null
  company?: string | null
  phone?: string | null
  timezone: string
  created_at: string
  display_name: string
}

export type AssignableContact = Omit<Customer360Contact, "display_name"> & {
  display_name?: string
}

export type ContactsResponse = {
  data: AssignableContact[]
  count: number
}

export type AccountContactAssignmentResponse = {
  account_id: string
  assigned_count: number
  unassigned_count: number
  contact_ids: string[]
}

export type Customer360ChannelSummary = {
  channel: string
  label: string
  count: number
  status: string
  detail: string
}

export type Customer360NextAction = {
  title: string
  reason: string
  source: string
  priority: string
}

export type Customer360OpenWork = {
  id: string
  source: string
  title: string
  contact_id?: string | null
  contact_name?: string | null
  status: string
  created_at: string
}

export type Customer360ProspectingBrief = {
  snapshot_id: string
  contact_id: string
  account_summary: string
  suggested_next_action?: string | null
  email_draft_available: boolean
  voice_opener_available: boolean
  created_at: string
}

export type Customer360TimelineEvent = {
  id: string
  source: string
  event_type: string
  title: string
  detail: string
  contact_id?: string | null
  contact_name?: string | null
  timestamp: string
}

export type Customer360AccountProfile = {
  account: Customer360Account
  contacts: Customer360Contact[]
  channel_summaries: Record<string, Customer360ChannelSummary>
  next_best_action?: Customer360NextAction | null
  open_work: Customer360OpenWork[]
  prospecting_brief?: Customer360ProspectingBrief | null
  timeline: Customer360TimelineEvent[]
}

export function listCustomer360Accounts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) params.set("search", search.trim())

  return signalloopRequest<Customer360AccountsResponse>(
    `/api/v1/customer-360/accounts?${params.toString()}`,
  )
}

export function listContacts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) params.set("search", search.trim())

  return signalloopRequest<ContactsResponse>(
    `/api/v1/contacts/?${params.toString()}`,
  )
}

export function getCustomer360AccountProfile(accountId: string) {
  return signalloopRequest<Customer360AccountProfile>(
    `/api/v1/customer-360/accounts/${accountId}`,
  )
}

export function createAccount(input: AccountWriteInput) {
  return signalloopRequest<Customer360Account>("/api/v1/accounts", {
    method: "POST",
    idempotent: true,
    body: input,
  })
}

export function updateAccount(accountId: string, input: AccountWriteInput) {
  return signalloopRequest<Customer360Account>(`/api/v1/accounts/${accountId}`, {
    method: "PATCH",
    body: input,
  })
}

export function assignContactsToAccount(
  accountId: string,
  contactIds: string[],
) {
  return signalloopRequest<AccountContactAssignmentResponse>(
    `/api/v1/accounts/${accountId}/contacts`,
    {
      method: "POST",
      body: { contact_ids: contactIds },
    },
  )
}

export function unassignContactFromAccount(
  accountId: string,
  contactId: string,
) {
  return signalloopRequest<AccountContactAssignmentResponse>(
    `/api/v1/accounts/${accountId}/contacts/${contactId}`,
    {
      method: "DELETE",
    },
  )
}
