import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import { TrendingUp, TrendingDown, Users, Calendar, AlertTriangle, Activity } from "lucide-react"
import { engagehubRequest, getWorkspaceId } from "@/lib/engagehub-api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

// ── Types ──────────────────────────────────────────────────────────────────────

interface KpiMetrics {
  contacts_processed: number
  intent_signals: number
  qualified_contacts: number
  bookings_confirmed: number
  provider_errors: number
  booking_sla_met: number
  booking_sla_breached: number
  signal_yield_rate: number
  conversion_rate: number
  booking_sla_compliance_pct: number
}

interface KpiSummaryResponse {
  current_period: KpiMetrics
  prior_period: KpiMetrics
  delta_pct: KpiMetrics
}

interface KpiTrendBucket {
  period_start: string
  period_end: string
  contacts_processed: number
  intent_signals: number
  qualified_contacts: number
  bookings_confirmed: number
  provider_errors: number
  booking_sla_met: number
  booking_sla_breached: number
  signal_yield_rate: number
  conversion_rate: number
  booking_sla_compliance_pct: number
}

type DatePreset = "7d" | "30d" | "90d"
type Granularity = "weekly" | "biweekly" | "monthly"

// ── Helpers ────────────────────────────────────────────────────────────────────

function toIsoDate(d: Date) {
  return d.toISOString().split("T")[0]
}

function getDateRange(preset: DatePreset): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  if (preset === "7d") start.setDate(end.getDate() - 7)
  else if (preset === "30d") start.setDate(end.getDate() - 30)
  else start.setDate(end.getDate() - 90)
  return { start: toIsoDate(start), end: toIsoDate(end) }
}

function DeltaBadge({ value }: { value: number }) {
  const formatted = value === 0 ? "0%" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`
  if (value > 0) {
    return (
      <Badge className="bg-green-100 text-green-800 gap-1">
        <TrendingUp className="h-3 w-3" />
        {formatted}
      </Badge>
    )
  }
  if (value < 0) {
    return (
      <Badge className="bg-red-100 text-red-800 gap-1">
        <TrendingDown className="h-3 w-3" />
        {formatted}
      </Badge>
    )
  }
  return <Badge variant="secondary">{formatted}</Badge>
}

function formatShortDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function KpiDashboardPage() {
  const [datePreset, setDatePreset] = useState<DatePreset>("30d")
  const [granularity, setGranularity] = useState<Granularity>("weekly")
  const [campaignId, setCampaignId] = useState<string>("all")

  const wsId = getWorkspaceId()
  const { start, end } = useMemo(() => getDateRange(datePreset), [datePreset])

  function buildParams(extra?: Record<string, string>) {
    const p = new URLSearchParams({ start, end, granularity })
    if (campaignId !== "all") p.set("campaign_id", campaignId)
    if (extra) Object.entries(extra).forEach(([k, v]) => p.set(k, v))
    return p.toString()
  }

  const summaryQuery = useQuery<KpiSummaryResponse>({
    queryKey: ["kpi-summary", wsId, start, end, granularity, campaignId],
    queryFn: () =>
      engagehubRequest<KpiSummaryResponse>(
        `/api/v1/workspaces/${wsId}/kpis/summary?${buildParams()}`,
      ),
  })

  const trendQuery = useQuery<KpiTrendBucket[]>({
    queryKey: ["kpi-trend", wsId, start, end, granularity, campaignId],
    queryFn: () =>
      engagehubRequest<KpiTrendBucket[]>(
        `/api/v1/workspaces/${wsId}/kpis/trend?${buildParams()}`,
      ),
  })

  const summary = summaryQuery.data
  const trend = trendQuery.data ?? []
  const isLoading = summaryQuery.isLoading || trendQuery.isLoading
  const isError = summaryQuery.isError || trendQuery.isError

  const summaryCards = summary
    ? [
        {
          title: "Contacts Processed",
          value: summary.current_period.contacts_processed.toLocaleString(),
          delta: summary.delta_pct.contacts_processed,
          icon: <Users className="h-5 w-5 text-muted-foreground" />,
        },
        {
          title: "Signal Yield Rate",
          value: `${(summary.current_period.signal_yield_rate * 100).toFixed(1)}%`,
          delta: summary.delta_pct.signal_yield_rate * 100,
          icon: <Activity className="h-5 w-5 text-muted-foreground" />,
        },
        {
          title: "Conversion Rate",
          value: `${(summary.current_period.conversion_rate * 100).toFixed(1)}%`,
          delta: summary.delta_pct.conversion_rate * 100,
          icon: <TrendingUp className="h-5 w-5 text-muted-foreground" />,
        },
        {
          title: "Booking SLA Compliance",
          value: `${(summary.current_period.booking_sla_compliance_pct * 100).toFixed(1)}%`,
          delta: summary.delta_pct.booking_sla_compliance_pct * 100,
          icon: <Calendar className="h-5 w-5 text-muted-foreground" />,
        },
      ]
    : []

  const chartData = trend.map((b) => ({
    label: formatShortDate(b.period_start),
    contacts: b.contacts_processed,
    signalYield: +(b.signal_yield_rate * 100).toFixed(2),
    conversion: +(b.conversion_rate * 100).toFixed(2),
    slaCompliance: +(b.booking_sla_compliance_pct * 100).toFixed(2),
  }))

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">KPI Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Weekly operating rhythm — performance at a glance
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          {/* Date preset buttons */}
          <div className="flex rounded-md border overflow-hidden">
            {(["7d", "30d", "90d"] as DatePreset[]).map((p) => (
              <button
                key={p}
                onClick={() => setDatePreset(p)}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  datePreset === p
                    ? "bg-primary text-primary-foreground"
                    : "bg-background hover:bg-muted"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Granularity */}
          <Select value={granularity} onValueChange={(v) => setGranularity(v as Granularity)}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="Granularity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="biweekly">Biweekly</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
            </SelectContent>
          </Select>

          {/* Campaign filter — placeholder; wire up to campaign list API if needed */}
          <Select value={campaignId} onValueChange={setCampaignId}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="All campaigns" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All campaigns</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Error banner */}
      {isError && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Failed to load KPI data. Please try again.
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => {
              summaryQuery.refetch()
              trendQuery.refetch()
            }}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardHeader className="pb-2">
                  <div className="h-4 w-24 rounded bg-muted" />
                </CardHeader>
                <CardContent>
                  <div className="h-8 w-20 rounded bg-muted" />
                </CardContent>
              </Card>
            ))
          : summaryCards.map((card) => (
              <Card key={card.title}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {card.title}
                  </CardTitle>
                  {card.icon}
                </CardHeader>
                <CardContent className="flex items-end justify-between gap-2">
                  <span className="text-2xl font-bold">{card.value}</span>
                  <DeltaBadge value={card.delta} />
                </CardContent>
              </Card>
            ))}
      </div>

      {/* Trend chart */}
      <Card>
        <CardHeader>
          <CardTitle>Trend</CardTitle>
          <CardDescription>
            {start} → {end} · {granularity}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-72 items-center justify-center">
              <p className="text-sm text-muted-foreground">Loading chart…</p>
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex h-72 items-center justify-center">
              <p className="text-sm text-muted-foreground">No data for this period.</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 4, right: 24, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 12 }}
                  className="text-muted-foreground"
                />
                <YAxis tick={{ fontSize: 12 }} className="text-muted-foreground" />
                <Tooltip
                  contentStyle={{ fontSize: 12 }}
                  formatter={(value: number, name: string) => {
                    if (name === "contacts") return [value.toLocaleString(), "Contacts"]
                    return [`${value}%`, name]
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="contacts"
                  name="Contacts"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="signalYield"
                  name="Signal Yield %"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="conversion"
                  name="Conversion %"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="slaCompliance"
                  name="SLA Compliance %"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Provider errors callout */}
      {summary && summary.current_period.provider_errors > 0 && (
        <div className="flex items-center gap-2 rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>
            <strong>{summary.current_period.provider_errors}</strong> provider error
            {summary.current_period.provider_errors !== 1 ? "s" : ""} detected in this period.
            Check the audit log for details.
          </span>
        </div>
      )}
    </div>
  )
}
