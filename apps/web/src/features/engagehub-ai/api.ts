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

export type ExperimentRecommendation = {
  id: string
  title: string
  hypothesis: string
  primary_metric: string
  variants: string[]
  holdout_percent: number
  eligible_count: number
  status: string
}

export type AuditReplayItem = {
  id: string
  event_name: string
  resource_type: string | null
  resource_id: string | null
  actor_role: string | null
  summary: string
  created_at: string
  payload: Record<string, unknown>
}

export type ProviderHealth = {
  id: string
  provider: string
  channel: string
  status: string
  success_count: number
  failure_count: number
  last_event_at: string | null
  recommended_action: string
}

export type PipelineRisk = {
  id: string
  contact_id: string
  contact_name: string
  company: string | null
  risk_level: string
  risk_score: number
  reasons: string[]
  recommended_action: string
}

export type EngagementOverview = {
  generated_at: string
  next_best_actions: NextBestAction[]
  unified_inbox: UnifiedInboxItem[]
  journey: JourneyCanvas
  knowledge_gaps: KnowledgeGap[]
  offer_recommendations: OfferRecommendation[]
  experiment_recommendations: ExperimentRecommendation[]
  audit_replay: AuditReplayItem[]
  provider_health: ProviderHealth[]
  pipeline_risks: PipelineRisk[]
}

export function getEngagementOverview() {
  return engagehubRequest<EngagementOverview>(
    "/api/v1/engagement-intelligence/overview",
  )
}
