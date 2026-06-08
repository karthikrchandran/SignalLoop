import type { LucideIcon } from "lucide-react"
import { CheckCircle2, Loader2, PauseCircle, PlugZap, TriangleAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { ChatbotChannel, ChatbotChannelStatus } from "@/features/chatbot/api"

type VisibleStatus = ChatbotChannelStatus | "disconnected" | "connecting"

type ChannelCardProps = {
  title: string
  description: string
  icon: LucideIcon
  channel?: ChatbotChannel
  fallbackStatus: VisibleStatus
  busy?: boolean
  onEdit: () => void
  onToggle: () => void
}

const statusMeta: Record<VisibleStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  connected: { label: "Connected", variant: "default" },
  connecting: { label: "Connecting", variant: "secondary" },
  disabled: { label: "Inactive", variant: "secondary" },
  disconnected: { label: "Disconnected", variant: "outline" },
  draft: { label: "Disconnected", variant: "outline" },
  error: { label: "Error", variant: "destructive" },
  pending_approval: { label: "Pending approval", variant: "secondary" },
}

const statusIcon = (status: VisibleStatus) => {
  if (status === "connected") return CheckCircle2
  if (status === "error") return TriangleAlert
  if (status === "disabled") return PauseCircle
  if (status === "connecting") return Loader2
  return PlugZap
}

const missingLabel = (value: string) => {
  if (value === "webhook secret" || value === "verify_token") return "webhook verification"
  if (value === "page_id") return "page ID"
  if (value === "phone_number_id") return "phone number ID"
  if (value === "bot_username") return "bot username"
  if (value === "redirect_url") return "redirect URL"
  return value
}

const missingPriority = [
  "activation",
  "provider credential",
  "page ID",
  "phone number ID",
  "bot username",
  "redirect URL",
  "webhook verification",
]

const formatList = (items: string[]) => {
  if (items.length === 0) return ""
  if (items.length === 1) return items[0]
  if (items.length === 2) return `${items[0]} and ${items[1]}`
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`
}

const priorityIndex = (value: string) => {
  const index = missingPriority.indexOf(value)
  return index === -1 ? missingPriority.length : index
}

const readinessLabel = (channel?: ChatbotChannel) => {
  if (!channel) return "Needs provider credential"
  if (channel.readiness.ready) return "Ready for live traffic"
  const labels = Array.from(new Set(channel.readiness.missing.map(missingLabel))).sort(
    (first, second) => priorityIndex(first) - priorityIndex(second),
  )
  if (labels.length === 0) return "Needs channel recovery"
  return `Needs ${formatList(labels)}`
}

export function ChannelCard({
  title,
  description,
  icon: Icon,
  channel,
  fallbackStatus,
  busy = false,
  onEdit,
  onToggle,
}: ChannelCardProps) {
  const status: VisibleStatus = busy ? "connecting" : channel?.status ?? fallbackStatus
  const meta = statusMeta[status]
  const StatusIcon = statusIcon(status)
  const isConnected = channel?.is_active && channel.status === "connected"
  const webhookPath = channel?.readiness.webhook_url_path ?? "Webhook path appears after connect"

  return (
    <Card className="rounded-lg">
      <CardHeader className="gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-muted">
              <Icon className="size-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <CardTitle className="truncate text-base">{title}</CardTitle>
              <p className="truncate text-sm text-muted-foreground">{description}</p>
            </div>
          </div>
          <Badge variant={meta.variant} className="gap-1">
            <StatusIcon className={status === "connecting" ? "size-3 animate-spin" : "size-3"} />
            {meta.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium">{readinessLabel(channel)}</p>
          <p className="truncate font-mono text-xs text-muted-foreground">{webhookPath}</p>
          <p className="text-xs text-muted-foreground">
            {channel?.last_verified_at ? `Verified ${new Date(channel.last_verified_at).toLocaleString()}` : "Not verified"}
          </p>
        </div>
        <div className="flex shrink-0 justify-end gap-2">
          {channel ? (
            <Button variant="outline" size="sm" onClick={onToggle} disabled={busy}>
              {isConnected ? "Disable" : "Activate"}
            </Button>
          ) : null}
          <Button size="sm" onClick={onEdit} disabled={busy}>
            {channel ? "Edit" : "Connect"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
