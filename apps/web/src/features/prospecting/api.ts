import { signalloopRequest } from "@/lib/signalloop-api"

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

export type ProspectingBulkResearchRequest = {
  contact_ids: string[]
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

export type ProspectingCampaign = {
  id: string
  name: string
  status: string
}

export type ProspectingCampaignListResponse = {
  data: ProspectingCampaign[]
  count: number
}

export type ProspectingSequence = {
  id: string
  campaign_id: string
  name: string
  active: boolean
  created_at: string
}

export type ProspectingSequenceListResponse = {
  data: ProspectingSequence[]
  count: number
}

export type ProspectingEnrollmentRequest = {
  contact_ids: string[]
  campaign_id: string
  sequence_id?: string | null
}

export type ProspectingEnrollmentResult = {
  selected_count: number
  campaign_added_count: number
  campaign_existing_count: number
  sequence_enrolled_count: number
  sequence_existing_count: number
  message: string
}

export function listContacts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) {
    params.set("search", search.trim())
  }
  return signalloopRequest<ContactListResponse>(`/api/v1/contacts/?${params.toString()}`)
}

export function listReadyContacts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) {
    params.set("search", search.trim())
  }
  return signalloopRequest<ProspectingReadyContactsResponse>(
    `/api/v1/prospecting/ready-contacts?${params.toString()}`,
  )
}

export function runProspectingResearch(input: ProspectingResearchRequest) {
  return signalloopRequest<ProspectingResearchResult>("/api/v1/prospecting/research", {
    method: "POST",
    idempotent: true,
    body: input,
  })
}

export function runBulkProspectingResearch(input: ProspectingBulkResearchRequest) {
  return signalloopRequest<ProspectingResearchListResponse>("/api/v1/prospecting/research/bulk", {
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
  return signalloopRequest<ProspectingResearchListResponse>(
    `/api/v1/prospecting/research${query ? `?${query}` : ""}`,
  )
}

export function listProspectingCampaigns() {
  return signalloopRequest<ProspectingCampaignListResponse>("/api/v1/campaigns/")
}

export function listProspectingSequences() {
  return signalloopRequest<ProspectingSequenceListResponse>("/api/v1/sequences/")
}

export function enrollProspects(input: ProspectingEnrollmentRequest) {
  return signalloopRequest<ProspectingEnrollmentResult>("/api/v1/prospecting/enroll", {
    method: "POST",
    idempotent: true,
    body: input,
  })
}
