import { signalloopRequest } from "@/lib/signalloop-api"

export type LeadMatchConfidence =
  | "EXACT_MATCH"
  | "HIGH_CONFIDENCE_FUZZY"
  | "AMBIGUOUS_CONFLICT"
  | "NEW_ENTITY"

export type LeadFitBand =
  | "HOT_OPPORTUNITY"
  | "HIGH_FIT"
  | "NURTURE"
  | "UNQUALIFIED"

export type DiscoveryProviderType =
  | "SANDBOX"
  | "APOLLO"
  | "CLAY"
  | "INTERNAL_AI"
  | "CUSTOM_WEBHOOK"

export type DiscoveredLead = {
  id: string
  workspace_id: string
  first_name: string
  last_name: string
  email: string
  phone: string | null
  title: string | null
  seniority: string | null
  department: string | null
  company_name: string
  company_domain: string
  industry: string | null
  employee_count: number | null
  revenue_range: string | null
  country: string | null
  region: string | null
  city: string | null
  tech_stack: string[]
  intent_signals: string[]
  source_provider: DiscoveryProviderType
  match_confidence: LeadMatchConfidence
  matched_account_id: string | null
  fit_score: number
  fit_band: LeadFitBand
  score_rationale: string | null
  conversation_starters: string[]
  is_promoted: boolean
  promoted_contact_id: string | null
  created_at: string
}

export type DiscoverySearchCriteria = {
  industries?: string[]
  revenue_min?: number
  revenue_max?: number
  employee_min?: number
  employee_max?: number
  countries?: string[]
  regions?: string[]
  job_titles?: string[]
  seniority_levels?: string[]
  tech_stack?: string[]
  keywords?: string[]
  limit?: number
}

export type DiscoverySearchResponse = {
  total: number
  leads: DiscoveredLead[]
  provider_used: DiscoveryProviderType
  criteria: DiscoverySearchCriteria
}

export type EnrichmentRequest = {
  domain?: string
  company_name?: string
  email?: string
  providers?: DiscoveryProviderType[]
}

export type EnrichmentResponse = {
  company_name: string
  domain: string
  industry: string | null
  employee_count: number | null
  revenue_range: string | null
  country: string | null
  region: string | null
  tech_stack: string[]
  intent_signals: string[]
  key_contacts: Array<{
    name: string
    title: string
    email: string
  }>
  enrichment_source: DiscoveryProviderType
}

export type LeadScoreContribution = {
  pillar: string
  points: number
  max_points: number
  reason: string
}

export type LeadScoringResponse = {
  fit_score: number
  fit_band: LeadFitBand
  contributions: LeadScoreContribution[]
  rationale: string
  conversation_starters: string[]
  suggested_channels: string[]
}

export type LeadPromotionRequest = {
  lead_id: string
  campaign_id?: string | null
  sequence_id?: string | null
  tags?: string[]
}

export type LeadPromotionResponse = {
  lead_id: string
  contact_id: string
  workspace_id: string
  enrolled_campaign_id: string | null
  enrolled_sequence_id: string | null
  status: string
  message: string
}

export function searchDiscoveredLeads(criteria: DiscoverySearchCriteria) {
  return signalloopRequest<DiscoverySearchResponse>(
    "/api/v1/lead-discovery/search",
    {
      method: "POST",
      body: criteria,
    },
  )
}

export function enrichLeadEntity(request: EnrichmentRequest) {
  return signalloopRequest<EnrichmentResponse>(
    "/api/v1/lead-discovery/enrich",
    {
      method: "POST",
      body: request,
    },
  )
}

export function scoreDiscoveredLead(leadId: string) {
  return signalloopRequest<LeadScoringResponse>(
    `/api/v1/lead-discovery/score/${leadId}`,
    {
      method: "POST",
    },
  )
}

export function promoteDiscoveredLead(request: LeadPromotionRequest) {
  return signalloopRequest<LeadPromotionResponse>(
    "/api/v1/lead-discovery/promote",
    {
      method: "POST",
      body: request,
    },
  )
}

export function listDiscoveryProviders() {
  return signalloopRequest<string[]>("/api/v1/lead-discovery/providers")
}
