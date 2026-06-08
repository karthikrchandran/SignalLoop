import { engagehubRequest } from "@/lib/engagehub-api"

export type NextBestAction = {
  id: string
  contact_id: string | null
  contact_name: string
  company: string | null
  channel: string
  priority: string
  score: number
  title: string
  reason: string
  recommended_action: string
  source: string
}

export type UnifiedInboxItem = {
  id: string
  source: string
  contact_id: string | null
  contact_name: string
  title: string
  summary: string
  priority: string
  status: string
  action_label: string
  next_best_action: string
  created_at: string
}

export type JourneyStage = {
  id: string
  label: string
  count: number
  description: string
}

export type JourneyEdge = {
  from_stage: string
  to_stage: string
  label: string
  count: number
}

export type JourneyCanvas = {
  stages: JourneyStage[]
  edges: JourneyEdge[]
}

export type KnowledgeGap = {
  id: string
  title: string
  source: string
  evidence_count: number
  evidence: string[]
  recommended_fix: string
  priority: string
}

export type OfferRecommendation = {
  id: string
  title: string
  reason: string
  recommended_offer: string
  priority: string
}

export type EngagementOverview = {
  generated_at: string
  next_best_actions: NextBestAction[]
  unified_inbox: UnifiedInboxItem[]
  journey: JourneyCanvas
  knowledge_gaps: KnowledgeGap[]
  offer_recommendations: OfferRecommendation[]
}

export function getEngagementOverview() {
  return engagehubRequest<EngagementOverview>(
    "/api/v1/engagement-intelligence/overview",
  )
}
