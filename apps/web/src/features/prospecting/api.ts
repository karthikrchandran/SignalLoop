import { engagehubRequest } from "@/lib/engagehub-api"

export type ProspectingContact = {
  id: string
  workspace_id: string
  email: string
  first_name: string | null
  last_name: string | null
  company: string | null
  phone: string | null
  timezone: string
  created_at: string
}

export type ContactListResponse = {
  data: ProspectingContact[]
  count: number
}

export type ProspectingPriority = "high" | "medium" | "low"

export type ProspectingReadyContact = ProspectingContact & {
  source_channel: string | null
  tags: string[]
  intents: string[]
  lead_score: number
  priority: ProspectingPriority
  priority_reasons: string[]
  handoff_source: string | null
}

export type ProspectingReadyContactsResponse = {
  data: ProspectingReadyContact[]
  count: number
}

export type ProspectingSource = {
  label: string
  summary: string
}

export type ProspectingResearchRequest = {
  contact_id: string
  company_url?: string | null
}

export type ProspectingResearchResult = {
  id: string
  contact_id: string
  company_url: string | null
  account_summary: string
  pain_points: string[]
  objections: string[]
  personalization_bullets: string[]
  suggested_next_action: string
  email_draft: string
  voice_opener: string
  sources: ProspectingSource[]
  created_at: string
}

export type ProspectingResearchListResponse = {
  data: ProspectingResearchResult[]
  count: number
}

export function listContacts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) {
    params.set("search", search.trim())
  }
  return engagehubRequest<ContactListResponse>(`/api/v1/contacts/?${params.toString()}`)
}

export function listReadyContacts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) {
    params.set("search", search.trim())
  }
  return engagehubRequest<ProspectingReadyContactsResponse>(
    `/api/v1/prospecting/ready-contacts?${params.toString()}`,
  )
}

export function runProspectingResearch(input: ProspectingResearchRequest) {
  return engagehubRequest<ProspectingResearchResult>("/api/v1/prospecting/research", {
    method: "POST",
    idempotent: true,
    body: input,
  })
}

export function listProspectingResearch(contactId?: string) {
  const params = new URLSearchParams()
  if (contactId) {
    params.set("contact_id", contactId)
  }
  const query = params.toString()
  return engagehubRequest<ProspectingResearchListResponse>(
    `/api/v1/prospecting/research${query ? `?${query}` : ""}`,
  )
}
