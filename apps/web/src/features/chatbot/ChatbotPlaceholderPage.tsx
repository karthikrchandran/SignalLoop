import type { LucideIcon } from "lucide-react"
import { Activity, AlertCircle, BarChart3, BookOpen, Inbox, Plug, SlidersHorizontal } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

type Metric = {
  label: string
  value: string
}

type ChatbotPlaceholderKind = "channels" | "knowledge" | "inbox" | "analytics" | "settings"

type ChatbotPlaceholderPageProps = {
  title: string
  eyebrow: string
  icon: LucideIcon
  status: string
  metrics: Metric[]
}

const screenCopy = {
  channels: {
    status: "Foundation ready",
    metrics: [
      { label: "Connected", value: "0" },
      { label: "Errors", value: "0" },
      { label: "Required", value: "2" },
    ],
  },
  knowledge: {
    status: "Index pending",
    metrics: [
      { label: "Sources", value: "0" },
      { label: "Chunks", value: "0" },
      { label: "Version", value: "1" },
    ],
  },
  inbox: {
    status: "No active escalations",
    metrics: [
      { label: "Open", value: "0" },
      { label: "Escalated", value: "0" },
      { label: "Resolved", value: "0" },
    ],
  },
  analytics: {
    status: "Awaiting traffic",
    metrics: [
      { label: "Conversations", value: "0" },
      { label: "Bot replies", value: "0" },
      { label: "Leads", value: "0" },
    ],
  },
  settings: {
    status: "Defaults active",
    metrics: [
      { label: "Token cap", value: "4k" },
      { label: "Retention", value: "90d" },
      { label: "Disclosure", value: "On" },
    ],
  },
} satisfies Record<ChatbotPlaceholderKind, { status: string; metrics: Metric[] }>

const iconMap = {
  channels: Plug,
  knowledge: BookOpen,
  inbox: Inbox,
  analytics: BarChart3,
  settings: SlidersHorizontal,
} satisfies Record<ChatbotPlaceholderKind, LucideIcon>

export function createChatbotPlaceholder(kind: ChatbotPlaceholderKind) {
  const labels = {
    channels: { title: "Channels", eyebrow: "Chatbot" },
    knowledge: { title: "Knowledge Base", eyebrow: "Chatbot" },
    inbox: { title: "Inbox", eyebrow: "Chatbot" },
    analytics: { title: "Analytics", eyebrow: "Chatbot" },
    settings: { title: "Settings", eyebrow: "Chatbot" },
  } satisfies Record<keyof typeof screenCopy, { title: string; eyebrow: string }>
  const copy = screenCopy[kind]
  return (
    <ChatbotPlaceholderPage
      title={labels[kind].title}
      eyebrow={labels[kind].eyebrow}
      icon={iconMap[kind]}
      status={copy.status}
      metrics={copy.metrics}
    />
  )
}

function ChatbotPlaceholderPage({
  title,
  eyebrow,
  icon: Icon,
  status,
  metrics,
}: ChatbotPlaceholderPageProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium text-muted-foreground">{eyebrow}</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Icon className="size-6 text-muted-foreground" />
            {title}
          </h1>
        </div>
        <Badge variant="secondary" className="gap-1">
          <Activity className="size-3" />
          {status}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {metrics.map((metric) => (
          <Card key={metric.label} className="rounded-lg">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {metric.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold tracking-tight">{metric.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="rounded-lg border border-dashed p-6">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <AlertCircle className="size-4" />
          <span>CBH-E1 foundation route</span>
        </div>
      </div>
    </div>
  )
}

export default ChatbotPlaceholderPage
