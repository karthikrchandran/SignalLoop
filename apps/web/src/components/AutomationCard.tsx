import { format } from "date-fns"
import {
  ArrowRight,
  Bot,
  CalendarCheck,
  ChevronRight,
  Mail,
  Phone,
  Shuffle,
  Zap,
} from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { ReasonCodeBadge } from "@/components/ReasonCodeBadge"

export interface TimelineEvent {
  id: string
  source_system: string
  event_type: string
  channel?: string | null
  timestamp: string // ISO-8601
  actor?: string | null
  outcome?: string | null
  reason_code?: string | null
  rule_ref?: string | null
  template_ref?: string | null
  confidence_tier?: string | null
  has_detail?: boolean
}

interface AutomationCardProps {
  event: TimelineEvent
  onClick?: (event: TimelineEvent) => void
  className?: string
}

// Map event channels / types to icons
function EventIcon({ event }: { event: TimelineEvent }) {
  const channel = event.channel?.toLowerCase()
  if (channel === "email") return <Mail className="h-4 w-4 text-blue-500" />
  if (channel === "voice" || channel === "call")
    return <Phone className="h-4 w-4 text-violet-500" />
  if (event.source_system === "routing_decisions")
    return <Shuffle className="h-4 w-4 text-orange-500" />
  if (event.source_system === "scheduling_requests")
    return <CalendarCheck className="h-4 w-4 text-emerald-500" />
  if (event.source_system === "signal_events")
    return <Zap className="h-4 w-4 text-purple-500" />
  if (event.source_system === "contact_state_history")
    return <Zap className="h-4 w-4 text-yellow-500" />
  return <Bot className="h-4 w-4 text-muted-foreground" />
}

function confidenceTierClass(tier?: string | null) {
  if (!tier) return ""
  switch (tier.toLowerCase()) {
    case "high":
      return "text-emerald-600 dark:text-emerald-400"
    case "medium":
      return "text-amber-600 dark:text-amber-400"
    case "low":
      return "text-red-500 dark:text-red-400"
    default:
      return "text-muted-foreground"
  }
}

/**
 * A timeline card representing one automation event.
 * Shows: event type → reason code → template applied.
 * Clicking opens the explainability detail panel.
 */
export function AutomationCard({ event, onClick, className }: AutomationCardProps) {
  const ts = new Date(event.timestamp)
  const label = event.event_type.replace(/_/g, " ")

  return (
    <Card
      className={cn(
        "cursor-pointer transition-colors hover:bg-accent/50 border-l-4",
        event.source_system === "routing_decisions"
          ? "border-l-orange-400"
          : event.source_system === "scheduling_requests"
            ? "border-l-emerald-400"
            : event.source_system === "signal_events"
              ? "border-l-purple-400"
          : event.source_system === "contact_events"
            ? "border-l-blue-400"
            : "border-l-yellow-400",
        className,
      )}
      onClick={() => onClick?.(event)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.(event)
      }}
    >
      <CardContent className="flex items-start gap-3 py-3 px-4">
        {/* Icon */}
        <div className="mt-0.5 shrink-0">
          <EventIcon event={event} />
        </div>

        {/* Body */}
        <div className="min-w-0 flex-1">
          {/* Event type + channel */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-medium capitalize">{label}</span>
            {event.channel && (
              <span className="text-xs text-muted-foreground">
                via {event.channel}
              </span>
            )}
            {event.confidence_tier && (
              <span
                className={cn(
                  "text-xs font-medium",
                  confidenceTierClass(event.confidence_tier),
                )}
              >
                ({event.confidence_tier} confidence)
              </span>
            )}
          </div>

          {/* Flow: reason_code → template_ref */}
          {(event.reason_code || event.template_ref || event.outcome) && (
            <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
              {event.reason_code && (
                <ReasonCodeBadge code={event.reason_code} />
              )}
              {event.reason_code && event.template_ref && (
                <ArrowRight className="h-3 w-3 shrink-0" />
              )}
              {event.template_ref && (
                <span className="font-mono text-xs text-foreground/80">
                  {event.template_ref}
                </span>
              )}
              {event.outcome && !event.template_ref && (
                <span className="text-xs">→ {event.outcome}</span>
              )}
              {event.rule_ref && (
                <span className="text-xs text-muted-foreground">
                  rule: {event.rule_ref}
                </span>
              )}
            </div>
          )}

          {/* Timestamp */}
          <div className="mt-1 text-xs text-muted-foreground">
            {format(ts, "MMM d, yyyy · HH:mm")}
          </div>
        </div>

        {/* Detail chevron */}
        {event.has_detail && (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </CardContent>
    </Card>
  )
}
