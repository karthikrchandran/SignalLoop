import { CheckCircle2, Loader2, TriangleAlert, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ChatbotKnowledgeSource } from "@/features/chatbot/api"

type IndexingProgressBannerProps = {
  sources: ChatbotKnowledgeSource[]
  dismissed: boolean
  onDismiss: () => void
}

export function IndexingProgressBanner({
  sources,
  dismissed,
  onDismiss,
}: IndexingProgressBannerProps) {
  const active = sources.filter((source) => source.status === "indexing" || source.status === "pending")
  const failed = sources.filter((source) => source.status === "failed")
  const stale = sources.filter((source) => source.status === "stale")
  if (dismissed && active.length === 0 && failed.length === 0 && stale.length === 0) {
    return null
  }
  if (active.length === 0 && failed.length === 0 && stale.length === 0) {
    return null
  }
  const Icon = failed.length > 0 ? TriangleAlert : active.length > 0 ? Loader2 : CheckCircle2
  const label = failed.length > 0
    ? `${failed.length} failed`
    : active.length > 0
      ? `${active.length} indexing`
      : `${stale.length} stale`

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/40 px-4 py-3 text-sm">
      <div className="flex min-w-0 items-center gap-3">
        <Icon className={active.length > 0 ? "size-4 animate-spin text-muted-foreground" : "size-4 text-muted-foreground"} />
        <span className="font-medium">{label}</span>
      </div>
      {active.length === 0 ? (
        <Button variant="ghost" size="icon" onClick={onDismiss}>
          <X className="size-4" />
          <span className="sr-only">Dismiss</span>
        </Button>
      ) : null}
    </div>
  )
}
