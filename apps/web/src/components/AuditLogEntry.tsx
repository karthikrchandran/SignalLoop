import { format } from "date-fns"
import { Clock, UserRound } from "lucide-react"

import { Badge } from "@/components/ui/badge"

interface AuditLogEntryProps {
  timestamp: string
  sourceSystem: string
  actor?: string | null
}

export function AuditLogEntry({ timestamp, sourceSystem, actor }: AuditLogEntryProps) {
  return (
    <div className="rounded-md border px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <Badge variant="secondary" className="font-mono text-xs">
          {sourceSystem}
        </Badge>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          {format(new Date(timestamp), "PPP HH:mm:ss")}
        </span>
      </div>
      {actor && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <UserRound className="h-3.5 w-3.5" />
          {actor}
        </div>
      )}
    </div>
  )
}
