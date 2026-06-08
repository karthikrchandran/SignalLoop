import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type ChatbotDeadLetter, listChatbotDeadLetters, retryChatbotDeadLetter } from "@/features/chatbot/api"

function channelLabel(value: string) {
  return value
    .split("_")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ")
}

function relativeAge(value: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000))
  if (minutes < 1) return "now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function DeadLettersPage() {
  const [rows, setRows] = useState<ChatbotDeadLetter[]>([])
  const [loading, setLoading] = useState(true)
  const [retryingId, setRetryingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await listChatbotDeadLetters()
      setRows(response.data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load dead letters")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const stats = useMemo(() => {
    const topChannel = rows.reduce<Record<string, number>>((accumulator, row) => {
      accumulator[row.channel_type] = (accumulator[row.channel_type] || 0) + 1
      return accumulator
    }, {})
    const channel = Object.entries(topChannel).sort((a, b) => b[1] - a[1])[0]?.[0]
    const oldest = rows.slice().sort((a, b) => new Date(a.failed_at).getTime() - new Date(b.failed_at).getTime())[0]
    return {
      failed: rows.length,
      retriesToday: rows.reduce((total, row) => total + row.attempt_count, 0),
      topChannel: channel ? channelLabel(channel) : "None",
      oldestFailed: oldest ? relativeAge(oldest.failed_at) : "None",
    }
  }, [rows])

  const retry = async (row: ChatbotDeadLetter) => {
    setRetryingId(row.id)
    setError(null)
    try {
      await retryChatbotDeadLetter(row.id)
      setRows((current) => current.filter((item) => item.id !== row.id))
      toast.success("Dead-lettered message requeued")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to retry dead letter")
    } finally {
      setRetryingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Operator</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <AlertTriangle className="size-6 text-muted-foreground" />
            Messaging Dead Letters
          </h1>
          <p className="text-sm text-muted-foreground">Verified messages that failed all worker retries.</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading} className="gap-2">
          <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} />
          Refresh
        </Button>
      </div>

      {error ? <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Failed" value={String(stats.failed)} />
        <MetricCard label="Retry attempts" value={String(stats.retriesToday)} />
        <MetricCard label="Top channel" value={stats.topChannel} />
        <MetricCard label="Oldest failed" value={stats.oldestFailed} />
      </div>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Dead-letter queue</h2>
        {loading ? (
          <Skeleton className="h-72" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Message ID</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Last error</TableHead>
                <TableHead>Attempts</TableHead>
                <TableHead>Failed at</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">No dead-lettered messaging events.</TableCell>
                </TableRow>
              ) : (
                rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-48 truncate font-medium">{row.provider_message_id}</TableCell>
                    <TableCell>{channelLabel(row.channel_type)}</TableCell>
                    <TableCell className="max-w-72 truncate">{row.last_error}</TableCell>
                    <TableCell><Badge variant="secondary">{row.attempt_count}</Badge></TableCell>
                    <TableCell>{relativeAge(row.failed_at)}</TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void retry(row)}
                        disabled={retryingId === row.id}
                        className="gap-2"
                      >
                        <RotateCcw className={retryingId === row.id ? "size-4 animate-spin" : "size-4"} />
                        Retry
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="truncate text-3xl font-semibold tracking-tight">{value}</div>
      </CardContent>
    </Card>
  )
}
