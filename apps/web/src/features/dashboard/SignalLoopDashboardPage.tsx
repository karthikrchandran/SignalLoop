import {
  Activity,
  Bot,
  CalendarClock,
  CircleAlert,
  Clock3,
  Inbox,
  MessageSquareText,
  RefreshCw,
  Send,
  Users,
  Workflow,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import WorkspaceHeader from "@/components/layout/WorkspaceHeader"
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
  type CampaignRecord,
  formatCampaignDate,
  getCampaignLifecycleLabel,
  normalizeCampaignStatus,
  useCampaignsWorkspace,
} from "@/features/campaigns/campaign-data"
import {
  type ChatbotAnalytics,
  type ChatbotChannel,
  getChatbotAnalytics,
  listChatbotChannels,
} from "@/features/chatbot/api"
import {
  listSchedulingRequests,
  type SchedulingRequest,
} from "@/features/scheduling/api"
import { getWorkspaceId, signalloopRequest } from "@/lib/signalloop-api"

type DatePreset = "7d" | "30d" | "90d"

type KpiMetrics = {
  contacts_processed: number
  intent_signals: number
  qualified_contacts: number
  bookings_confirmed: number
  provider_errors: number
  booking_sla_compliance_pct: number
}

type KpiSummaryResponse = {
  current_period: KpiMetrics
}

type SourceState = "idle" | "loading" | "ready" | "empty" | "unavailable"

type SourceStates = {
  analytics: SourceState
  channels: SourceState
  scheduling: SourceState
  kpis: SourceState
}

const emptySourceStates: SourceStates = {
  analytics: "loading",
  channels: "loading",
  scheduling: "loading",
  kpis: "loading",
}

function dateRange(preset: DatePreset) {
  const end = new Date()
  const start = new Date(end)
  start.setDate(end.getDate() - Number(preset.replace("d", "")) + 1)
  return {
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  }
}

function number(value: number | null | undefined) {
  return (value ?? 0).toLocaleString("en-US")
}

function percentage(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—"
  return `${value > 1 ? value.toFixed(0) : (value * 100).toFixed(0)}%`
}

function channelLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
    .replace(" Business", "")
}

function scheduleStatusLabel(value: SchedulingRequest["status"]) {
  return value === "link_sent"
    ? "Link sent"
    : value.charAt(0).toUpperCase() + value.slice(1)
}

function statusClass(value: string) {
  if (["connected", "ready", "booked", "active"].includes(value)) {
    return "bg-emerald-500/10 text-emerald-700"
  }
  if (["error", "cancelled", "paused"].includes(value)) {
    return "bg-amber-500/10 text-amber-700"
  }
  return "bg-muted text-muted-foreground"
}

function EmptyState({ children }: { children: string }) {
  return (
    <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
      {children}
    </p>
  )
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string
  value: string
  detail: string
  icon: typeof Activity
}) {
  return (
    <Card className="gap-3 py-4">
      <CardContent className="px-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-tight">
              {value}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
          </div>
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Icon className="size-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function SourceNote({ state, label }: { state: SourceState; label: string }) {
  if (state === "unavailable")
    return (
      <p className="text-xs text-amber-700">{label} is not available yet.</p>
    )
  if (state === "loading")
    return (
      <p className="text-xs text-muted-foreground">
        Loading {label.toLowerCase()}…
      </p>
    )
  return null
}

export default function SignalLoopDashboardPage() {
  const [preset, setPreset] = useState<DatePreset>("30d")
  const [analytics, setAnalytics] = useState<ChatbotAnalytics | null>(null)
  const [channels, setChannels] = useState<ChatbotChannel[]>([])
  const [scheduling, setScheduling] = useState<SchedulingRequest[]>([])
  const [kpis, setKpis] = useState<KpiMetrics | null>(null)
  const [sourceStates, setSourceStates] =
    useState<SourceStates>(emptySourceStates)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const {
    campaigns,
    counts,
    loading: campaignsLoading,
    error: campaignsError,
    refresh: refreshCampaigns,
  } = useCampaignsWorkspace()
  const range = useMemo(() => dateRange(preset), [preset])

  const loadDashboardData = useCallback(async () => {
    setIsRefreshing(true)
    setSourceStates(emptySourceStates)
    const workspaceId = getWorkspaceId()
    const kpiQuery = new URLSearchParams({
      start: range.from,
      end: range.to,
      granularity: "weekly",
    })
    const results = await Promise.allSettled([
      getChatbotAnalytics({ from: range.from, to: range.to }),
      listChatbotChannels(workspaceId),
      listSchedulingRequests({ limit: 100 }),
      signalloopRequest<KpiSummaryResponse>(
        `/api/v1/workspaces/${workspaceId}/kpis/summary?${kpiQuery.toString()}`,
      ),
    ])

    const [analyticsResult, channelResult, schedulingResult, kpiResult] =
      results
    if (analyticsResult.status === "fulfilled") {
      setAnalytics(analyticsResult.value)
      setSourceStates((current) => ({
        ...current,
        analytics:
          analyticsResult.value.totals.conversations ||
          analyticsResult.value.timeseries.length
            ? "ready"
            : "empty",
      }))
    } else {
      setAnalytics(null)
      setSourceStates((current) => ({ ...current, analytics: "unavailable" }))
    }
    if (channelResult.status === "fulfilled") {
      setChannels(channelResult.value.data)
      setSourceStates((current) => ({
        ...current,
        channels: channelResult.value.data.length ? "ready" : "empty",
      }))
    } else {
      setChannels([])
      setSourceStates((current) => ({ ...current, channels: "unavailable" }))
    }
    if (schedulingResult.status === "fulfilled") {
      setScheduling(schedulingResult.value.data)
      setSourceStates((current) => ({
        ...current,
        scheduling: schedulingResult.value.data.length ? "ready" : "empty",
      }))
    } else {
      setScheduling([])
      setSourceStates((current) => ({ ...current, scheduling: "unavailable" }))
    }
    if (kpiResult.status === "fulfilled") {
      setKpis(kpiResult.value.current_period)
      setSourceStates((current) => ({ ...current, kpis: "ready" }))
    } else {
      setKpis(null)
      setSourceStates((current) => ({ ...current, kpis: "unavailable" }))
    }
    setIsRefreshing(false)
  }, [range.from, range.to])

  useEffect(() => {
    void loadDashboardData()
  }, [loadDashboardData])

  const refresh = () => {
    refreshCampaigns()
    void loadDashboardData()
  }

  const recentCampaigns = useMemo(() => campaigns.slice(0, 6), [campaigns])
  const scheduleCounts = useMemo(
    () =>
      scheduling.reduce<Record<SchedulingRequest["status"], number>>(
        (result, item) => {
          result[item.status] += 1
          return result
        },
        { pending: 0, link_sent: 0, booked: 0, cancelled: 0 },
      ),
    [scheduling],
  )
  const connectedChannels = channels.filter(
    (channel) => channel.is_active && channel.readiness.ready,
  ).length
  const assignedHandoffs = scheduling.filter(
    (item) => item.assigned_to_email,
  ).length
  const kpiContacts = kpis?.contacts_processed ?? 0
  const hasAnalyticsActivity = Boolean(
    analytics &&
      (analytics.totals.conversations ||
        analytics.totals.leads_captured ||
        analytics.totals.escalations),
  )

  return (
    <div className="space-y-6">
      <WorkspaceHeader
        eyebrow="SignalLoop · Admin command center"
        title="Agent activity, in one operating view"
        description="Monitor what autonomous agents are doing, where conversations are coming from, and which opportunities need a person or a calendar next."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <fieldset className="flex rounded-md border bg-background p-1">
              <legend className="sr-only">Reporting range</legend>
              {(["7d", "30d", "90d"] as DatePreset[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPreset(value)}
                  className={`rounded px-3 py-1.5 text-xs font-medium ${preset === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                >
                  {value.replace("d", " days")}
                </button>
              ))}
            </fieldset>
            <Button
              variant="outline"
              size="sm"
              onClick={refresh}
              disabled={isRefreshing || campaignsLoading}
            >
              <RefreshCw className={isRefreshing ? "animate-spin" : ""} />{" "}
              Refresh
            </Button>
          </div>
        }
      />

      <section
        aria-label="Command center metrics"
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6"
      >
        <MetricCard
          label="Active campaigns"
          value={number(counts.active)}
          detail={campaignsLoading ? "Loading campaigns" : "Running now"}
          icon={Workflow}
        />
        <MetricCard
          label="Contacts processed"
          value={kpis ? number(kpiContacts) : "—"}
          detail={
            kpis
              ? `Last ${preset.replace("d", " days")}`
              : "KPI feed not connected"
          }
          icon={Users}
        />
        <MetricCard
          label="ChatHub conversations"
          value={analytics ? number(analytics.totals.conversations) : "—"}
          detail={
            hasAnalyticsActivity
              ? `${percentage(analytics?.totals.containment_rate)} contained`
              : "No activity recorded"
          }
          icon={MessageSquareText}
        />
        <MetricCard
          label="Leads captured"
          value={analytics ? number(analytics.totals.leads_captured) : "—"}
          detail="Across inbound channels"
          icon={Inbox}
        />
        <MetricCard
          label="Meetings booked"
          value={number(scheduleCounts.booked)}
          detail={`${number(scheduleCounts.pending + scheduleCounts.link_sent)} need attention`}
          icon={CalendarClock}
        />
        <MetricCard
          label="Escalations"
          value={analytics ? number(analytics.totals.escalations) : "—"}
          detail="Human follow-up required"
          icon={CircleAlert}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>Campaign performance</CardTitle>
                <CardDescription>
                  Lifecycle coverage for the campaigns your agents are running.
                </CardDescription>
              </div>
              <Badge variant="outline">{number(campaigns.length)} total</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            {campaignsError ? (
              <p className="text-sm text-amber-700">
                Campaign data is unavailable: {campaignsError}
              </p>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { label: "Draft", value: counts.draft },
                { label: "Running", value: counts.active },
                { label: "Paused", value: counts.paused },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-muted/50 p-3">
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                  <p className="mt-1 text-xl font-semibold">
                    {number(item.value)}
                  </p>
                </div>
              ))}
            </div>
            {recentCampaigns.length ? (
              <div className="divide-y rounded-lg border">
                {recentCampaigns.map((campaign: CampaignRecord) => {
                  const status = normalizeCampaignStatus(campaign.status)
                  return (
                    <div
                      key={campaign.id}
                      className="flex items-center justify-between gap-4 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {campaign.name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Created {formatCampaignDate(campaign.created_at)}
                        </p>
                      </div>
                      <Badge className={statusClass(campaign.status)}>
                        {status
                          ? getCampaignLifecycleLabel(status)
                          : campaign.status}
                      </Badge>
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState>
                No campaigns yet. Agents will appear here once a campaign is
                created.
              </EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>ChatHub traffic</CardTitle>
                <CardDescription>
                  Channel mix, containment, leads, and handoffs for the selected
                  range.
                </CardDescription>
              </div>
              <Bot className="size-5 text-primary" />
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            <SourceNote
              state={sourceStates.analytics}
              label="ChatHub analytics"
            />
            {analytics && hasAnalyticsActivity ? (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div>
                    <p className="text-xs text-muted-foreground">
                      Conversations
                    </p>
                    <p className="mt-1 text-lg font-semibold">
                      {number(analytics.totals.conversations)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Contained</p>
                    <p className="mt-1 text-lg font-semibold">
                      {percentage(analytics.totals.containment_rate)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Leads</p>
                    <p className="mt-1 text-lg font-semibold">
                      {number(analytics.totals.leads_captured)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Opt-outs</p>
                    <p className="mt-1 text-lg font-semibold">
                      {number(analytics.totals.opt_outs)}
                    </p>
                  </div>
                </div>
                <div className="space-y-3">
                  {analytics.channel_breakdown.map((row) => {
                    const share = analytics.totals.conversations
                      ? Math.round(
                          (row.conversations / analytics.totals.conversations) *
                            100,
                        )
                      : 0
                    return (
                      <div key={row.channel_type}>
                        <div className="mb-1 flex justify-between text-xs">
                          <span>{channelLabel(row.channel_type)}</span>
                          <span className="text-muted-foreground">
                            {number(row.conversations)} ·{" "}
                            {number(row.lead_captured)} leads
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary"
                            style={{ width: `${share}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            ) : (
              <EmptyState>
                No ChatHub traffic recorded for this period.
              </EmptyState>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>Channel health</CardTitle>
                <CardDescription>
                  Whether inbound channels are configured, active, and ready for
                  agents.
                </CardDescription>
              </div>
              <Activity className="size-5 text-primary" />
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <SourceNote
              state={sourceStates.channels}
              label="Channel configuration"
            />
            {channels.length ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2 text-sm">
                  <span>Ready channels</span>
                  <span className="font-semibold">
                    {connectedChannels}/{channels.length}
                  </span>
                </div>
                {channels.map((channel) => (
                  <div
                    key={channel.id}
                    className="flex items-center justify-between gap-3 border-b pb-3 last:border-0 last:pb-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {channel.display_name ||
                          channelLabel(channel.channel_type)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {channel.is_active ? "Active" : "Inactive"}
                      </p>
                    </div>
                    <Badge className={statusClass(channel.readiness.status)}>
                      {channel.readiness.ready
                        ? "Ready"
                        : channel.readiness.status.replace(/_/g, " ")}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState>
                No channels configured. Connect a channel before agents can
                receive inbound work.
              </EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>AI agent operations</CardTitle>
                <CardDescription>
                  Efficiency signals for autonomous work, separate from sales
                  targets.
                </CardDescription>
              </div>
              <Workflow className="size-5 text-primary" />
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            <SourceNote state={sourceStates.kpis} label="Agent KPI feed" />
            {kpis ? (
              <div className="grid grid-cols-2 gap-3">
                {[
                  {
                    label: "Contacts processed",
                    value: number(kpis.contacts_processed),
                  },
                  {
                    label: "Intent signals",
                    value: number(kpis.intent_signals),
                  },
                  {
                    label: "Qualified",
                    value: number(kpis.qualified_contacts),
                  },
                  {
                    label: "SLA compliance",
                    value: percentage(kpis.booking_sla_compliance_pct),
                  },
                  {
                    label: "Provider errors",
                    value: number(kpis.provider_errors),
                  },
                  {
                    label: "Confirmed bookings",
                    value: number(kpis.bookings_confirmed),
                  },
                ].map((item) => (
                  <div key={item.label} className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground">
                      {item.label}
                    </p>
                    <p className="mt-1 text-lg font-semibold">{item.value}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState>
                No agent KPI activity recorded for this period.
              </EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>Calendar handoffs</CardTitle>
                <CardDescription>
                  Agent-generated scheduling requests and the people responsible
                  for the next step.
                </CardDescription>
              </div>
              <CalendarClock className="size-5 text-primary" />
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            <SourceNote
              state={sourceStates.scheduling}
              label="Scheduling queue"
            />
            {scheduling.length ? (
              <>
                <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                  {(
                    [
                      "pending",
                      "link_sent",
                      "booked",
                      "cancelled",
                    ] as SchedulingRequest["status"][]
                  ).map((status) => (
                    <div key={status} className="rounded-lg bg-muted/50 p-2">
                      <p className="text-xs text-muted-foreground">
                        {scheduleStatusLabel(status)}
                      </p>
                      <p className="mt-1 text-lg font-semibold">
                        {number(scheduleCounts[status])}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="space-y-2">
                  {scheduling.slice(0, 4).map((request) => (
                    <div
                      key={request.id}
                      className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {request.assigned_to_email || "Unassigned handoff"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {request.meeting_datetime
                            ? formatCampaignDate(request.meeting_datetime)
                            : `${request.source.replace(/_/g, " ")} · awaiting time`}
                        </p>
                      </div>
                      <Badge className={statusClass(request.status)}>
                        {scheduleStatusLabel(request.status)}
                      </Badge>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {number(assignedHandoffs)} of {number(scheduling.length)}{" "}
                  requests have an assigned owner.
                </p>
              </>
            ) : (
              <EmptyState>
                No scheduling handoffs yet. Agent booking requests will appear
                here for assignment and follow-up.
              </EmptyState>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground">
        <Clock3 className="size-4" />
        Reporting range: {range.from} to {range.to}
        <span className="text-border">·</span>
        <Send className="size-4" />
        {sourceStates.analytics === "unavailable" ||
        sourceStates.channels === "unavailable"
          ? "Some feeds are not connected yet; empty states are intentional."
          : "Metrics update from connected agent and channel feeds."}
      </div>
    </div>
  )
}
