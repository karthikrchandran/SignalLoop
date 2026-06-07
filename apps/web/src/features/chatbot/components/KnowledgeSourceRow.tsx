import { FileText, Globe2, HelpCircle, MessageSquareText, RefreshCw, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { TableCell, TableRow } from "@/components/ui/table"
import type { ChatbotKnowledgeSource, ChatbotKnowledgeSourceType } from "@/features/chatbot/api"

type KnowledgeSourceRowProps = {
  source: ChatbotKnowledgeSource
  busy?: boolean
  onReindex: () => void
  onDelete: () => void
}

const typeLabel: Record<ChatbotKnowledgeSourceType, string> = {
  website: "Website",
  document: "Document",
  faq: "FAQ",
  manual_text: "Manual text",
  qa_pair: "Q&A",
}

const TypeIcon = ({ type }: { type: ChatbotKnowledgeSourceType }) => {
  if (type === "website") return <Globe2 className="size-4 text-muted-foreground" />
  if (type === "document") return <FileText className="size-4 text-muted-foreground" />
  if (type === "qa_pair") return <HelpCircle className="size-4 text-muted-foreground" />
  return <MessageSquareText className="size-4 text-muted-foreground" />
}

const statusVariant = (status: ChatbotKnowledgeSource["status"]) => {
  if (status === "ready") return "default"
  if (status === "failed") return "destructive"
  if (status === "stale") return "secondary"
  return "outline"
}

export function KnowledgeSourceRow({
  source,
  busy = false,
  onReindex,
  onDelete,
}: KnowledgeSourceRowProps) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex min-w-64 items-center gap-3">
          <TypeIcon type={source.source_type} />
          <div className="min-w-0">
            <div className="truncate font-medium">{source.title}</div>
            <div className="truncate text-xs text-muted-foreground">{typeLabel[source.source_type]}</div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={statusVariant(source.status)}>{source.status}</Badge>
      </TableCell>
      <TableCell>{source.chunk_count}</TableCell>
      <TableCell>{source.indexed_at ? new Date(source.indexed_at).toLocaleString() : "-"}</TableCell>
      <TableCell className="max-w-64 truncate text-muted-foreground">{source.error_message || "-"}</TableCell>
      <TableCell>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="icon" onClick={onReindex} disabled={busy}>
            <RefreshCw className={busy ? "size-4 animate-spin" : "size-4"} />
            <span className="sr-only">Re-index</span>
          </Button>
          <Button variant="outline" size="icon" onClick={onDelete} disabled={busy}>
            <Trash2 className="size-4" />
            <span className="sr-only">Delete</span>
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}
