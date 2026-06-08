import {
  ArrowRight,
  BrainCircuit,
  ClipboardList,
  GitBranch,
  Inbox,
  Lightbulb,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react"
import type { ReactNode } from "react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  type EngagementOverview,
  getEngagementOverview,
  type JourneyEdge,
  type JourneyStage,
  type KnowledgeGap,
  type NextBestAction,
  type OfferRecommendation,
  type UnifiedInboxItem,
} from "@/features/engagehub-ai/api"

const priorityVariant = (
  priority: string,
): "default" | "destructive" | "outline" => {
  if (priority === "high") return "destructive"
  if (priority === "medium") return "default"
  return "outline"
}

const formatDate = (value: string) => new Date(value).toLocaleString()

export default function EngageHubAiPage() {
  const [overview, setOverview] = useState<EngagementOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getEngagementOverview()
      setOverview(response)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load EngageHub AI",
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  const totalJourneyContacts = useMemo(
    () =>
      overview?.journey.stages.reduce(
        (total, stage) => total + stage.count,
        0,
      ) ?? 0,
    [overview],
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
            <BrainCircuit className="h-7 w-7 text-primary" />
            EngageHub AI
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Prioritize actions, unify channel work, inspect journey movement,
            and close knowledge gaps from one operational surface.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => void loadOverview()}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Next actions"
          value={String(overview?.next_best_actions.length ?? 0)}
          icon={<Sparkles className="h-4 w-4" />}
        />
        <MetricCard
          label="Work queue"
          value={String(overview?.unified_inbox.length ?? 0)}
          icon={<Inbox className="h-4 w-4" />}
        />
        <MetricCard
          label="Journey signals"
          value={String(totalJourneyContacts)}
          icon={<GitBranch className="h-4 w-4" />}
        />
        <MetricCard
          label="Gaps"
          value={String(overview?.knowledge_gaps.length ?? 0)}
          icon={<Lightbulb className="h-4 w-4" />}
        />
      </div>

      {loading && !overview ? (
        <div className="flex items-center gap-2 rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading EngageHub AI...
        </div>
      ) : (
        <>
          <NextBestActions actions={overview?.next_best_actions ?? []} />
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <UnifiedWorkQueue items={overview?.unified_inbox ?? []} />
            <JourneyCanvas
              edges={overview?.journey.edges ?? []}
              stages={overview?.journey.stages ?? []}
            />
          </div>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <KnowledgeGapFinder gaps={overview?.knowledge_gaps ?? []} />
            <OfferRecommendations
              recommendations={overview?.offer_recommendations ?? []}
              generatedAt={overview?.generated_at ?? null}
            />
          </div>
        </>
      )}
    </div>
  )
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">{label}</p>
        <span className="text-muted-foreground">{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function NextBestActions({ actions }: { actions: NextBestAction[] }) {
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={<Sparkles className="h-5 w-5 text-primary" />}
        title="Next Best Actions"
        description="Ranked action recommendations across voice, chatbot, prospecting, and sequences."
      />
      <div className="grid gap-4 xl:grid-cols-3">
        {actions.length ? (
          actions.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))
        ) : (
          <EmptyState message="No high-priority actions found for this workspace." />
        )}
      </div>
    </section>
  )
}

function ActionCard({ action }: { action: NextBestAction }) {
  return (
    <Card className="border-border/70">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{action.title}</CardTitle>
            <CardDescription>{action.contact_name}</CardDescription>
          </div>
          <Badge variant={priorityVariant(action.priority)}>
            {action.priority}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{action.channel}</Badge>
          <Badge variant="outline">Score {action.score}</Badge>
          {action.company && <Badge variant="outline">{action.company}</Badge>}
        </div>
        <p className="text-sm leading-6 text-muted-foreground">
          {action.reason}
        </p>
        <div className="rounded-md bg-muted/30 p-3 text-sm">
          {action.recommended_action}
        </div>
      </CardContent>
    </Card>
  )
}

function UnifiedWorkQueue({ items }: { items: UnifiedInboxItem[] }) {
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={<Inbox className="h-5 w-5 text-primary" />}
        title="Unified work queue"
        description="AI and human follow-up work from chat, calls, and prospecting."
      />
      <div className="space-y-3">
        {items.length ? (
          items.map((item) => <WorkQueueItem key={item.id} item={item} />)
        ) : (
          <EmptyState message="No unified work queue items are waiting." />
        )}
      </div>
    </section>
  )
}

function WorkQueueItem({ item }: { item: UnifiedInboxItem }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">{item.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {item.contact_name} · {item.source} · {item.status}
          </p>
        </div>
        <Badge variant={priorityVariant(item.priority)}>{item.priority}</Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">
        {item.summary}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{item.action_label}</Badge>
        <span className="text-xs text-muted-foreground">
          {formatDate(item.created_at)}
        </span>
      </div>
    </div>
  )
}

function JourneyCanvas({
  edges,
  stages,
}: {
  edges: JourneyEdge[]
  stages: JourneyStage[]
}) {
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={<GitBranch className="h-5 w-5 text-primary" />}
        title="Journey orchestration canvas"
        description="Current movement through capture, research, sequence, voice, and handoff stages."
      />
      <div className="rounded-lg border p-4">
        <div className="space-y-3">
          {stages.map((stage, index) => (
            <div key={stage.id}>
              <JourneyStageRow stage={stage} />
              {index < stages.length - 1 && (
                <JourneyEdgeRow edge={edges[index]} />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function JourneyStageRow({ stage }: { stage: JourneyStage }) {
  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-medium">{stage.label}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {stage.description}
          </p>
        </div>
        <span className="text-2xl font-semibold">{stage.count}</span>
      </div>
    </div>
  )
}

function JourneyEdgeRow({ edge }: { edge?: JourneyEdge }) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground">
      <ArrowRight className="h-4 w-4" />
      <span>{edge ? `${edge.label}: ${edge.count}` : "Next stage"}</span>
    </div>
  )
}

function KnowledgeGapFinder({ gaps }: { gaps: KnowledgeGap[] }) {
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={<Lightbulb className="h-5 w-5 text-primary" />}
        title="Knowledge gap finder"
        description="Repeated questions that should be added to the shared knowledge base."
      />
      <div className="space-y-3">
        {gaps.length ? (
          gaps.map((gap) => <KnowledgeGapCard key={gap.id} gap={gap} />)
        ) : (
          <EmptyState message="No knowledge gaps found from current conversations." />
        )}
      </div>
    </section>
  )
}

function KnowledgeGapCard({ gap }: { gap: KnowledgeGap }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">{gap.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {gap.evidence_count} evidence item(s) from {gap.source}
          </p>
        </div>
        <Badge variant={priorityVariant(gap.priority)}>{gap.priority}</Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">
        {gap.recommended_fix}
      </p>
      <div className="mt-3 space-y-2">
        {gap.evidence.map((item) => (
          <div key={item} className="rounded-md bg-muted/30 p-3 text-sm">
            {item}
          </div>
        ))}
      </div>
    </div>
  )
}

function OfferRecommendations({
  generatedAt,
  recommendations,
}: {
  generatedAt: string | null
  recommendations: OfferRecommendation[]
}) {
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={<ClipboardList className="h-5 w-5 text-primary" />}
        title="Offer recommendations"
        description="Offer pack guidance based on the active gaps and buyer questions."
      />
      <div className="space-y-3">
        {recommendations.length ? (
          recommendations.map((recommendation) => (
            <div key={recommendation.id} className="rounded-lg border p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{recommendation.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {recommendation.reason}
                  </p>
                </div>
                <Badge variant={priorityVariant(recommendation.priority)}>
                  {recommendation.priority}
                </Badge>
              </div>
              <div className="mt-3 rounded-md bg-muted/30 p-3 text-sm">
                {recommendation.recommended_offer}
              </div>
            </div>
          ))
        ) : (
          <EmptyState message="No offer recommendations yet." />
        )}
        {generatedAt && (
          <p className="text-xs text-muted-foreground">
            Generated {formatDate(generatedAt)}
          </p>
        )}
      </div>
    </section>
  )
}

function SectionHeader({
  description,
  icon,
  title,
}: {
  description: string
  icon: ReactNode
  title: string
}) {
  return (
    <div>
      <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
        {icon}
        {title}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
      {message}
    </div>
  )
}
