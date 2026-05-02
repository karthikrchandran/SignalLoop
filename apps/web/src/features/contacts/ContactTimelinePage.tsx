import { useEffect, useState } from "react"
import { format } from "date-fns"
import { RefreshCw, X } from "lucide-react"

import { AutomationCard, type TimelineEvent } from "@/components/AutomationCard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { ReasonCodeBadge } from "@/components/ReasonCodeBadge"
import { engagehubRequest } from "@/lib/engagehub-api"

// ─── Types ───────────────────────────────────────────────────────────────────

interface TimelineEventDetail extends TimelineEvent {
  rule_name?: string | null
  rule_condition?: string | null
  signal_summary?: string | null
  transcript_excerpt?: string | null
}

interface TimelinePage {
  data: TimelineEvent[]
  count: number
  next_cursor?: string | null
}

// ─── Filters ─────────────────────────────────────────────────────────────────

const EVENT_TYPE_OPTIONS = [
  { value: "", label: "All event types" },
  { value: "state_transition", label: "State transition" },
  { value: "email_sent", label: "Email sent" },
  { value: "email_opened", label: "Email opened" },
  { value: "call_initiated", label: "Call initiated" },
  { value: "sequence_step", label: "Sequence step" },
  { value: "routing", label: "Routing decision" },
]

// ─── Component ───────────────────────────────────────────────────────────────

interface ContactTimelinePageProps {
  contactId: string
  contactName?: string
  campaignId?: string
}

export default function ContactTimelinePage({
  contactId,
  contactName,
  campaignId,
}: ContactTimelinePageProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [eventType, setEventType] = useState("")
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const [page, setPage] = useState(1)
  const limit = 50

  // Detail panel
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null)
  const [detail, setDetail] = useState<TimelineEventDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // ─── Fetch timeline ───────────────────────────────────────────────────────

  async function fetchTimeline(resetPage = false) {
    const currentPage = resetPage ? 1 : page
    if (resetPage) setPage(1)

    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      params.set("page", String(currentPage))
      params.set("limit", String(limit))
      if (campaignId) params.set("campaign_id", campaignId)
      if (eventType) params.set("event_type", eventType)
      if (fromDate) params.set("from", new Date(fromDate).toISOString())
      if (toDate) params.set("to", new Date(toDate).toISOString())

      const result = await engagehubRequest<TimelinePage>(
        `/api/v1/contacts/${contactId}/timeline?${params.toString()}`,
      )
      if (resetPage || currentPage === 1) {
        setEvents(result.data)
      } else {
        setEvents((prev) => [...prev, ...result.data])
      }
      setTotal(result.count)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timeline")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (contactId) {
      void fetchTimeline(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactId, campaignId])

  // ─── Fetch detail ─────────────────────────────────────────────────────────

  async function handleEventClick(event: TimelineEvent) {
    setSelectedEvent(event)
    setDetail(null)

    if (!event.has_detail) {
      setDetail(event as TimelineEventDetail)
      return
    }

    setDetailLoading(true)
    try {
      const d = await engagehubRequest<TimelineEventDetail>(
        `/api/v1/contacts/${contactId}/timeline/${event.id}`,
      )
      setDetail(d)
    } catch {
      setDetail(event as TimelineEventDetail)
    } finally {
      setDetailLoading(false)
    }
  }

  function applyFilters() {
    void fetchTimeline(true)
  }

  function resetFilters() {
    setEventType("")
    setFromDate("")
    setToDate("")
    // useEffect will re-run when eventType, fromDate, toDate change,
    // but we call fetchTimeline directly for instant reset
    setTimeout(() => void fetchTimeline(true), 0)
  }

  const hasMore = events.length < total

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {contactName ? `${contactName} — Timeline` : "Contact Timeline"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {total} event{total !== 1 ? "s" : ""} recorded
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void fetchTimeline(true)}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Event type</label>
          <Select value={eventType} onValueChange={setEventType}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All event types" />
            </SelectTrigger>
            <SelectContent>
              {EVENT_TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">From</label>
          <Input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="w-40"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">To</label>
          <Input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="w-40"
          />
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={applyFilters} disabled={loading}>
            Apply
          </Button>
          <Button size="sm" variant="ghost" onClick={resetFilters}>
            Reset
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Events list */}
      <div className="flex flex-col gap-2 overflow-y-auto">
        {events.length === 0 && !loading && (
          <p className="text-center text-sm text-muted-foreground py-12">
            No events recorded yet.
          </p>
        )}

        {events.map((event) => (
          <AutomationCard
            key={event.id}
            event={event}
            onClick={handleEventClick}
          />
        ))}

        {hasMore && (
          <Button
            variant="outline"
            className="mt-2 self-center"
            disabled={loading}
            onClick={() => {
              const nextPage = page + 1
              setPage(nextPage)
              void fetchTimeline()
            }}
          >
            {loading ? "Loading…" : `Load more (${total - events.length} remaining)`}
          </Button>
        )}

        {loading && events.length === 0 && (
          <div className="flex justify-center py-12">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>

      {/* Detail Sheet (360 px side panel) */}
      <Sheet
        open={!!selectedEvent}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedEvent(null)
            setDetail(null)
          }
        }}
      >
        <SheetContent className="w-[360px] sm:w-[360px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>
              {detail
                ? detail.event_type.replace(/_/g, " ")
                : "Event detail"}
            </SheetTitle>
          </SheetHeader>

          {detailLoading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!detailLoading && detail && (
            <div className="mt-4 flex flex-col gap-4 text-sm">
              {/* Timestamp */}
              <DetailRow label="Time">
                {format(new Date(detail.timestamp), "PPP · HH:mm:ss")}
              </DetailRow>

              {/* Source */}
              <DetailRow label="Source">
                <Badge variant="secondary" className="font-mono text-xs">
                  {detail.source_system}
                </Badge>
              </DetailRow>

              {/* Channel */}
              {detail.channel && (
                <DetailRow label="Channel">{detail.channel}</DetailRow>
              )}

              {/* Actor */}
              {detail.actor && (
                <DetailRow label="Actor">{detail.actor}</DetailRow>
              )}

              {/* Outcome */}
              {detail.outcome && (
                <DetailRow label="Outcome">{detail.outcome}</DetailRow>
              )}

              {/* Reason code */}
              {detail.reason_code && (
                <DetailRow label="Reason code">
                  <ReasonCodeBadge code={detail.reason_code} />
                </DetailRow>
              )}

              {/* Confidence */}
              {detail.confidence_tier && (
                <DetailRow label="Confidence">{detail.confidence_tier}</DetailRow>
              )}

              {/* Template */}
              {detail.template_ref && (
                <DetailRow label="Template">
                  <span className="font-mono text-xs">{detail.template_ref}</span>
                </DetailRow>
              )}

              {/* Rule name */}
              {detail.rule_name && (
                <DetailRow label="Rule">{detail.rule_name}</DetailRow>
              )}

              {/* Rule condition */}
              {detail.rule_condition && (
                <DetailRow label="Condition">
                  <pre className="whitespace-pre-wrap rounded bg-muted px-2 py-1 text-xs">
                    {detail.rule_condition}
                  </pre>
                </DetailRow>
              )}

              {/* Signal summary */}
              {detail.signal_summary && (
                <DetailRow label="Signal summary">
                  <pre className="whitespace-pre-wrap rounded bg-muted px-2 py-1 text-xs">
                    {detail.signal_summary}
                  </pre>
                </DetailRow>
              )}

              {/* Transcript */}
              {detail.transcript_excerpt && (
                <DetailRow label="Transcript excerpt">
                  <p className="rounded bg-muted px-2 py-1 text-xs italic">
                    {detail.transcript_excerpt}
                  </p>
                </DetailRow>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function DetailRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  )
}
