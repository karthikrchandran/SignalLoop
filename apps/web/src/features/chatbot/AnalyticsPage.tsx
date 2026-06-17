import { useEffect, useMemo, useState } from "react"
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { BarChart3, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type ChatbotAnalytics, getChatbotAnalytics } from "@/features/chatbot/api"

function defaultRange() {
  const end = new Date()
  const start = new Date(end)
  start.setDate(end.getDate() - 6)
  return {
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  }
}

function channelLabel(value: string) {
  return value
    .split("_")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ")
}

function updatedLabel(value?: string) {
  if (!value) return "Not updated"
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000))
  if (minutes < 1) return "Updated now"
  if (minutes < 60) return `Updated ${minutes}m ago`
  return `Updated ${Math.floor(minutes / 60)}h ago`
}

export default function AnalyticsPage() {
  const [range, setRange] = useState(defaultRange)
  const [data, setData] = useState<ChatbotAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await getChatbotAnalytics(range))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load messaging analytics")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const channelChart = useMemo(
    () =>
      (data?.channel_breakdown || []).map((row) => ({
        channel: channelLabel(row.channel_type).replace(" Business", ""),
        conversations: row.conversations,
        escalated: row.escalated,
        leads: row.lead_captured,
      })),
    [data?.channel_breakdown],
  )
  const conversionStages = useMemo(() => {
    if (!data) return []
    return [
      { label: "Conversations", value: data.conversion_funnel.conversations },
      { label: "Leads captured", value: data.conversion_funnel.leads_captured },
      { label: "Prospecting researched", value: data.conversion_funnel.prospecting_researched },
      { label: "Added to campaign", value: data.conversion_funnel.added_to_campaign },
      { label: "Sequence enrolled", value: data.conversion_funnel.sequence_enrolled },
      { label: "Voice follow-up", value: data.conversion_funnel.voice_followups },
    ]
  }, [data])
  const hasAnyAnalytics = Boolean(
    data &&
      (data.totals.conversations > 0 ||
        data.totals.leads_captured > 0 ||
        data.totals.escalations > 0 ||
        data.timeseries.length > 0 ||
        data.channel_breakdown.length > 0),
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Messaging Hub</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <BarChart3 className="size-6 text-muted-foreground" />
            Analytics
          </h1>
          <p className="text-sm text-muted-foreground">Messaging performance for the current workspace.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="grid gap-1.5">
            <Label htmlFor="analytics-from">From</Label>
            <Input id="analytics-from" type="date" value={range.from} onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="analytics-to">To</Label>
            <Input id="analytics-to" type="date" value={range.to} onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))} />
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading} className="gap-2">
            <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} />
            Refresh
          </Button>
          <Badge variant="secondary">{updatedLabel(data?.updated_at)}</Badge>
        </div>
      </div>

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

      {loading && !data ? (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
          </div>
          <Skeleton className="h-80" />
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Conversations" value={String(data.totals.conversations)} />
            <MetricCard label="Containment" value={`${data.totals.containment_rate}%`} />
            <MetricCard label="Leads Captured" value={String(data.totals.leads_captured)} />
            <MetricCard label="Escalations" value={String(data.totals.escalations)} />
          </div>

          {data && !hasAnyAnalytics ? (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              No messaging analytics for this range.
            </div>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Conversion funnel</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                {conversionStages.map((stage, index) => (
                  <div key={stage.label} className="min-w-0 rounded-lg border bg-muted/30 p-3">
                    <p className="truncate text-xs font-medium text-muted-foreground">{stage.label}</p>
                    <div className="mt-2 flex items-baseline justify-between gap-2">
                      <span className="text-2xl font-semibold tracking-tight">{stage.value}</span>
                      {index > 0 ? (
                        <span className="text-xs text-muted-foreground">
                          {conversionStages[index - 1]?.value
                            ? `${Math.round((stage.value / conversionStages[index - 1].value) * 100)}%`
                            : "0%"}
                        </span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Conversations over time</CardTitle>
              </CardHeader>
              <CardContent className="h-80">
                {data.timeseries.length === 0 ? (
                  <EmptyChart />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.timeseries}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tickMargin={8} />
                      <YAxis allowDecimals={false} width={36} />
                      <Tooltip />
                      <Line type="monotone" dataKey="conversations" stroke="#2563eb" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="leads_captured" stroke="#16a34a" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Channel breakdown</CardTitle>
              </CardHeader>
              <CardContent className="h-80">
                {channelChart.length === 0 ? (
                  <EmptyChart />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={channelChart}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="channel" tickMargin={8} />
                      <YAxis allowDecimals={false} width={36} />
                      <Tooltip />
                      <Bar dataKey="conversations" fill="#2563eb" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="leads" fill="#16a34a" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="escalated" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <section className="space-y-3">
            <h2 className="text-base font-semibold">Outcome breakdown</h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Channel</TableHead>
                  <TableHead>Bot-resolved</TableHead>
                  <TableHead>Escalated</TableHead>
                  <TableHead>Lead-captured</TableHead>
                  <TableHead>Opted-out</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.channel_breakdown.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">No messaging analytics for this range.</TableCell>
                  </TableRow>
                ) : (
                  data.channel_breakdown.map((row) => (
                    <TableRow key={row.channel_type}>
                      <TableCell className="font-medium">{channelLabel(row.channel_type)}</TableCell>
                      <TableCell>{row.bot_resolved}</TableCell>
                      <TableCell>{row.escalated}</TableCell>
                      <TableCell>{row.lead_captured}</TableCell>
                      <TableCell>{row.opted_out}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </section>
        </>
      ) : null}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tracking-tight">{value}</div>
      </CardContent>
    </Card>
  )
}

function EmptyChart() {
  return (
    <div className="flex h-full items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
      No data for this range
    </div>
  )
}
