import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ReasonCodeBadgeProps {
  code: string | null | undefined
  className?: string
}

const REASON_CODE_COLORS: Record<string, string> = {
  // Positive / success signals
  high_intent: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300",
  opted_in: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300",
  converted: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300",

  // Neutral / informational
  scheduled: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300",
  campaign_enrolled: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300",
  sequence_started: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300",

  // Warning / caution
  low_engagement: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300",
  retry_scheduled: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300",
  paused: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300",

  // Negative / error
  unsubscribed: "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300",
  bounced: "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300",
  opted_out: "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300",
  invalid_contact: "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300",
}

const DEFAULT_COLOR =
  "bg-secondary text-secondary-foreground border-transparent"

/** Small badge that displays a reason_code with semantic colour coding. */
export function ReasonCodeBadge({ code, className }: ReasonCodeBadgeProps) {
  if (!code) return null

  const colorClass = REASON_CODE_COLORS[code.toLowerCase()] ?? DEFAULT_COLOR
  const label = code.replace(/_/g, " ")

  return (
    <Badge
      variant="outline"
      className={cn(colorClass, "capitalize font-normal", className)}
      title={code}
    >
      {label}
    </Badge>
  )
}
