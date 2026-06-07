import { MessageCircle, Phone, Send } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { ChatbotThreadSummary } from "@/features/chatbot/api"
import { cn } from "@/lib/utils"

const channelIcon = {
  facebook_messenger: MessageCircle,
  whatsapp_business: Phone,
  telegram: Send,
  linkedin_redirect: MessageCircle,
}

const statusLabel = {
  open: "Bot Active",
  escalated: "Escalated",
  agent_active: "Agent Active",
  resolved: "Resolved",
  bot_paused: "Opted Out",
}

const accentClass = {
  open: "border-l-sky-500",
  escalated: "border-l-amber-500",
  agent_active: "border-l-emerald-500",
  resolved: "border-l-muted",
  bot_paused: "border-l-slate-500",
}

function relativeTime(value?: string | null) {
  if (!value) return ""
  const diff = Date.now() - new Date(value).getTime()
  const minutes = Math.max(0, Math.floor(diff / 60000))
  if (minutes < 1) return "now"
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

type ThreadRowProps = {
  thread: ChatbotThreadSummary
  selected: boolean
  highlighted?: boolean
  onSelect: () => void
}

export function ThreadRow({ thread, selected, highlighted, onSelect }: ThreadRowProps) {
  const Icon = channelIcon[thread.channel_type]
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full border-l-4 border-b px-3 py-3 text-left transition-colors",
        accentClass[thread.status],
        selected ? "bg-muted" : "bg-background hover:bg-muted/60",
        highlighted ? "motion-safe:animate-pulse" : "",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate text-sm font-medium">{thread.lead?.name || thread.visitor_id}</span>
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">{relativeTime(thread.last_message_at)}</span>
      </div>
      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{thread.preview || "No messages yet"}</p>
      <div className="mt-2 flex items-center gap-2">
        <Badge variant={thread.status === "escalated" ? "destructive" : "secondary"}>{statusLabel[thread.status]}</Badge>
        {thread.is_opted_out ? <Badge variant="outline">Opted out</Badge> : null}
      </div>
    </button>
  )
}

