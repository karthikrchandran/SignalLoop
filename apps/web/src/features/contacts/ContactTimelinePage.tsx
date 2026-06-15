import { useEffect, useState, type ReactNode } from "react"
import { RefreshCw } from "lucide-react"

import { AuditLogEntry } from "@/components/AuditLogEntry"
import { AutomationCard, type TimelineEvent } from "@/components/AutomationCard"
import { ReasonCodeBadge } from "@/components/ReasonCodeBadge"
import { TranscriptSnippet } from "@/components/TranscriptSnippet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { signalloopRequest } from "@/lib/signalloop-api"

interface TimelineEventDetail extends TimelineEvent {
  reason_code_explanation?: string | null
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

interface TimelineFilters {
  eventTypes: string[]
  fromDate: string
  toDate: string
}

const EVENT_TYPE_OPTIONS = [
  { value: "state_transition", label: "State" },
  { value: "email_sent", label: "Email sent" },
  { value: "email_opened", label: "Email opened" },
  { value: "call_session", label: "Call" },
  { value: "signal", label: "Signal" },
  { value: "booking_event", label: "Booking" },
  { value: "routing", label: "Routing" },
]

interface ContactTimelinePageProps {
  contactId: string
  contactName?: string
  campaignId?: string
}

function startOfDayIso(value: string) {
  return new Date(`${value}T00:00:00.000`).toISOString()
}

function endOfDayIso(value: string) {
  return new Date(`${value}T23:59:59.999`).toISOString()
}

export default function ContactTimelinePage({
  contactId,
  contactName,
  campaignId,
}: ContactTimelinePageProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [total, setTotal] = useState(0)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [eventTypes, setEventTypes] = useState<string[]>([])
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const limit = 50

  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null)
  const [detail, setDetail] = useState<TimelineEventDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  async function fetchTimeline({
    reset = false,
    cursor = null,
    filters = { eventTypes, fromDate, toDate },
  }: {
    reset?: boolean
    cursor?: string | null
    filters?: TimelineFilters
  } = {}) {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      params.set("limit", String(limit))
      if (campaignId) params.set("campaign_id", campaignId)
      if (cursor) params.set("cursor", cursor)
      if (filters.eventTypes.length > 0) {
        params.set("event_type", filters.eventTypes.join(","))
      }
      if (filters.fromDate) params.set("from", startOfDayIso(filters.fromDate))
      if (filters.toDate) params.set("to", endOfDayIso(filters.toDate))

      const result = await signalloopRequest<TimelinePage>(
        `/api/v1/contacts/${contactId}/timeline?${params.toString()}`,
      )
      if (reset || !cursor) {
        setEvents(result.data)
      } else {
        setEvents((prev) => [...prev, ...result.data])
      }
      setTotal(result.count)
      setNextCursor(result.next_cursor ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timeline")
    } finally {
      setLoading(false)
    }
  }

  const eventTypesKey = eventTypes.join(",")

  useEffect(() => {
    if (contactId) {
      void fetchTimeline({ reset: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactId, campaignId, eventTypesKey, fromDate, toDate])

  async function handleEventClick(event: TimelineEvent) {
    setSelectedEvent(event)
    setDetail(null)

    if (!event.has_detail) {
      setDetail(event as TimelineEventDetail)
      return
    }

    setDetailLoading(true)
    try {
      const result = await signalloopRequest<TimelineEventDetail>(
        `/api/v1/contacts/${contactId}/timeline/${event.id}`,
      )
      setDetail(result)
    } catch {
      setDetail(event as TimelineEventDetail)
    } finally {
      setDetailLoading(false)
    }
  }

  function toggleEventType(value: string, checked: boolean) {
    setEventTypes((current) =>
      checked
        ? Array.from(new Set([...current, value]))
        : current.filter((item) => item !== value),
    )
  }

  function resetFilters() {
    setEventTypes([])
    setFromDate("")
    setToDate("")
  }

  const remaining = Math.max(total - events.length, 0)

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">
            {contactName ? `${contactName} Timeline` : "Contact Timeline"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {total} event{total !== 1 ? "s" : ""} recorded
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void fetchTimeline({ reset: true })}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
        <div className="flex min-w-72 flex-col gap-1">
          <label className="text-xs text-muted-foreground">Event types</label>
          <div className="flex flex-wrap gap-2 rounded-md border px-3 py-2">
            {EVENT_TYPE_OPTIONS.map((option) => (
              <label
                key={option.value}
                className="flex items-center gap-1.5 text-sm text-foreground"
              >
                <Checkbox
                  checked={eventTypes.includes(option.value)}
                  onCheckedChange={(checked) =>
                    toggleEventType(option.value, checked === true)
                  }
                />
                {option.label}
              </label>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">From</label>
          <Input
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            className="w-40"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">To</label>
          <Input
            type="date"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
            className="w-40"
          />
        </div>

        <Button size="sm" variant="ghost" onClick={resetFilters} disabled={loading}>
          Reset
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-2 overflow-y-auto">
        {events.length === 0 && !loading && (
          <p className="py-12 text-center text-sm text-muted-foreground">
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

        {nextCursor && (
          <Button
            variant="outline"
            className="mt-2 self-center"
            disabled={loading}
            onClick={() => void fetchTimeline({ cursor: nextCursor })}
          >
            {loading ? "Loading..." : `Load more (${remaining} remaining)`}
          </Button>
        )}

        {loading && events.length === 0 && (
          <div className="flex justify-center py-12">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>

      <Sheet
        open={!!selectedEvent}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedEvent(null)
            setDetail(null)
          }
        }}
      >
        <SheetContent className="w-[360px] overflow-y-auto sm:w-[360px]">
          <SheetHeader>
            <SheetTitle>
              {detail ? detail.event_type.replace(/_/g, " ") : "Event detail"}
            </SheetTitle>
          </SheetHeader>

          {detailLoading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!detailLoading && detail && (
            <div className="mt-4 flex flex-col gap-4 text-sm">
              <AuditLogEntry
                timestamp={detail.timestamp}
                sourceSystem={detail.source_system}
                actor={detail.actor}
              />

              {detail.channel && <DetailRow label="Channel">{detail.channel}</DetailRow>}

              {detail.outcome && <DetailRow label="Outcome">{detail.outcome}</DetailRow>}

              {detail.reason_code && (
                <DetailRow label="Reason code">
                  <ReasonCodeBadge code={detail.reason_code} />
                </DetailRow>
              )}

              {detail.reason_code_explanation && (
                <DetailRow label="Explanation">
                  {detail.reason_code_explanation}
                </DetailRow>
              )}

              {detail.confidence_tier && (
                <DetailRow label="Confidence">{detail.confidence_tier}</DetailRow>
              )}

              {detail.template_ref && (
                <DetailRow label="Template">
                  <span className="font-mono text-xs">{detail.template_ref}</span>
                </DetailRow>
              )}

              {detail.rule_name && <DetailRow label="Rule">{detail.rule_name}</DetailRow>}

              {detail.rule_condition && (
                <DetailRow label="Condition">
                  <pre className="whitespace-pre-wrap rounded bg-muted px-2 py-1 text-xs">
                    {detail.rule_condition}
                  </pre>
                </DetailRow>
              )}

              {detail.signal_summary && (
                <DetailRow label="Signal summary">
                  <pre className="whitespace-pre-wrap rounded bg-muted px-2 py-1 text-xs">
                    {detail.signal_summary}
                  </pre>
                </DetailRow>
              )}

              {detail.transcript_excerpt && (
                <TranscriptSnippet excerpt={detail.transcript_excerpt} />
              )}

              <DetailRow label="Event ID">
                <Badge variant="secondary" className="break-all font-mono text-xs">
                  {detail.id}
                </Badge>
              </DetailRow>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function DetailRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  )
}
