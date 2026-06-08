import { AlertCircle, Bot, CheckCircle2, Download, Inbox, RefreshCw, RotateCcw } from "lucide-react"
import { useNavigate } from "@tanstack/react-router"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { exportChatbotThreads, type ChatbotExportFormat } from "@/features/chatbot/api"
import { MessageBubble } from "@/features/chatbot/components/MessageBubble"
import { ReplyComposer } from "@/features/chatbot/components/ReplyComposer"
import { ThreadRow } from "@/features/chatbot/components/ThreadRow"
import { WhatsAppWindowBanner } from "@/features/chatbot/components/WhatsAppWindowBanner"
import { useChatThreads } from "@/features/chatbot/hooks/useChatThreads"

const statusOptions = [
  { value: "all", label: "All" },
  { value: "escalated", label: "Escalated" },
  { value: "open", label: "Bot" },
  { value: "resolved", label: "Resolved" },
] as const

const channelOptions = [
  { value: "all", label: "All channels" },
  { value: "whatsapp_business", label: "WhatsApp" },
  { value: "facebook_messenger", label: "Facebook" },
  { value: "telegram", label: "Telegram" },
] as const

type InboxPageProps = {
  threadId?: string | null
}

export default function InboxPage({ threadId }: InboxPageProps) {
  const navigate = useNavigate()
  const inbox = useChatThreads(threadId)
  const selected = inbox.detail

  const sendReply = async (message: string) => {
    try {
      await inbox.sendReply(message)
      toast.success("Reply sent")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to send reply")
    }
  }

  const resolve = async () => {
    await inbox.resolveSelected()
    toast.success("Thread resolved")
  }

  const reopen = async () => {
    await inbox.reopenSelected()
    toast.success("Thread reopened")
  }

  const downloadExport = async (format: ChatbotExportFormat) => {
    try {
      const { blob, filename } = await exportChatbotThreads(format, inbox.filters)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${format.toUpperCase()}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to export conversations")
    }
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-[620px] flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Messaging Hub</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Inbox className="size-6 text-muted-foreground" />
            Inbox
          </h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge variant={inbox.sseConnected ? "secondary" : "outline"}>
            {inbox.sseConnected ? "Live" : "Polling"}
          </Badge>
          <Button variant="outline" size="sm" onClick={() => void downloadExport("csv")} className="gap-2">
            <Download className="size-4" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => void downloadExport("json")} className="gap-2">
            <Download className="size-4" />
            JSON
          </Button>
          <Button variant="outline" size="sm" onClick={inbox.refresh} className="gap-2">
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
      </div>

      {inbox.error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {inbox.error}
        </div>
      ) : null}

      <div className="grid min-h-0 flex-1 overflow-hidden rounded-lg border bg-background lg:grid-cols-[380px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col border-r">
          <div className="space-y-3 border-b p-3">
            <div className="grid grid-cols-2 gap-2">
              <Select
                value={inbox.filters.status || "all"}
                onValueChange={(value) => inbox.setFilters((current) => ({ ...current, status: value as never }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={inbox.filters.channel_type || "all"}
                onValueChange={(value) => inbox.setFilters((current) => ({ ...current, channel_type: value as never }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {channelOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {inbox.loading ? (
              <div className="space-y-3 p-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-24 w-full" />
                ))}
              </div>
            ) : inbox.threads.length === 0 ? (
              <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
                Conversations appear here after connected channels receive messages.
              </div>
            ) : (
              inbox.threads.map((thread, index) => (
                <ThreadRow
                  key={thread.id}
                  thread={thread}
                  selected={thread.id === inbox.selectedThreadId}
                  highlighted={index === 0 && thread.status === "escalated"}
                  onSelect={() => {
                    inbox.setSelectedThreadId(thread.id)
                    void navigate({ to: "/chatbot/inbox/$threadId", params: { threadId: thread.id } })
                  }}
                />
              ))
            )}
          </div>
        </aside>

        <section className="flex min-h-0 flex-col">
          {!selected && !inbox.detailLoading ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a thread
            </div>
          ) : null}
          {inbox.detailLoading ? (
            <div className="space-y-3 p-4">
              <Skeleton className="h-12 w-1/2" />
              <Skeleton className="h-20 w-3/4" />
              <Skeleton className="ml-auto h-20 w-2/3" />
            </div>
          ) : selected ? (
            <>
              <div className="flex items-center justify-between gap-3 border-b p-4">
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold">{selected.lead?.name || selected.visitor_id}</h2>
                  <p className="text-sm text-muted-foreground">{selected.channel_type.replace("_", " ")}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={selected.status === "escalated" ? "destructive" : "secondary"}>{selected.status.replace("_", " ")}</Badge>
                  {selected.status === "resolved" ? (
                    <Button variant="outline" size="sm" onClick={reopen} className="gap-2">
                      <RotateCcw className="size-4" />
                      Reopen
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={resolve} className="gap-2">
                      <CheckCircle2 className="size-4" />
                      Resolve
                    </Button>
                  )}
                </div>
              </div>

              {selected.is_opted_out ? (
                <div className="border-b bg-muted/40 p-3 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="size-4" />
                    Visitor has opted out. Bot engagement is disabled for this channel visitor.
                  </div>
                </div>
              ) : null}

              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                {selected.messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
                    <Bot className="size-4" />
                    No messages yet
                  </div>
                ) : (
                  selected.messages.map((message) => <MessageBubble key={message.id} message={message} />)
                )}
              </div>

              {selected.status === "resolved" ? (
                <div className="border-t p-4 text-sm text-muted-foreground">Thread is resolved.</div>
              ) : selected.channel_type === "whatsapp_business" && !selected.is_whatsapp_window_open ? (
                <WhatsAppWindowBanner />
              ) : (
                <ReplyComposer disabled={selected.is_opted_out} onSend={sendReply} />
              )}
            </>
          ) : null}
        </section>
      </div>
    </div>
  )
}
