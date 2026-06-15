import { useCallback, useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { signalloopRequest } from "@/lib/signalloop-api"

// ─── Types ────────────────────────────────────────────────────────────────────

interface CampaignHealth {
  active_count: number
  success_count_1h: number
  success_count_24h: number
  failure_count_24h: number
  dead_letter_count: number
  provider_errors_by_type: Record<string, number>
}

interface DeadLetterItem {
  id: string
  contact_id: string
  action_type: string
  failure_reason: string | null
  retry_count: number
  first_failed_at: string
  retry_eligible: boolean
}

interface DeadLetterList {
  data: DeadLetterItem[]
  count: number
  page: number
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 30_000

function successRate(health: CampaignHealth): string {
  const total = health.success_count_24h + health.failure_count_24h
  if (total === 0) return "—"
  return `${Math.round((health.success_count_24h / total) * 100)}%`
}

function healthColor(health: CampaignHealth): string {
  if (health.dead_letter_count > 0) return "text-red-600"
  if (health.failure_count_24h > 0) return "text-yellow-600"
  return "text-green-600"
}

// ─── Component ────────────────────────────────────────────────────────────────

interface CampaignHealthPageProps {
  campaignId: string
}

export default function CampaignHealthPage({ campaignId }: CampaignHealthPageProps) {
  const [health, setHealth] = useState<CampaignHealth | null>(null)
  const [deadLetters, setDeadLetters] = useState<DeadLetterItem[]>([])
  const [dlTotal, setDlTotal] = useState(0)
  const [dlPage, setDlPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [secondsAgo, setSecondsAgo] = useState(0)
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})

  // Tick seconds-ago counter
  useEffect(() => {
    const id = setInterval(() => {
      if (lastUpdated) {
        setSecondsAgo(Math.round((Date.now() - lastUpdated.getTime()) / 1000))
      }
    }, 1000)
    return () => clearInterval(id)
  }, [lastUpdated])

  const fetchHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [h, dl] = await Promise.all([
        signalloopRequest<CampaignHealth>(
          `/api/v1/campaigns/${campaignId}/health`,
        ),
        signalloopRequest<DeadLetterList>(
          `/api/v1/campaigns/${campaignId}/dead-letters?page=${dlPage}`,
        ),
      ])
      setHealth(h)
      setDeadLetters(dl.data)
      setDlTotal(dl.count)
      setLastUpdated(new Date())
      setSecondsAgo(0)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load health data")
    } finally {
      setLoading(false)
    }
  }, [campaignId, dlPage])

  // Initial load + polling
  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [fetchHealth])

  async function handleRetry(itemId: string) {
    setActionLoading((prev) => ({ ...prev, [itemId]: true }))
    try {
      await signalloopRequest(
        `/api/v1/campaigns/${campaignId}/dead-letters/${itemId}/retry`,
        { method: "POST" },
      )
      await fetchHealth()
    } catch {
      // surface inline in future iteration
    } finally {
      setActionLoading((prev) => ({ ...prev, [itemId]: false }))
    }
  }

  async function handleDismiss(itemId: string) {
    setActionLoading((prev) => ({ ...prev, [itemId]: true }))
    try {
      await signalloopRequest(
        `/api/v1/campaigns/${campaignId}/dead-letters/${itemId}/dismiss`,
        { method: "POST" },
      )
      await fetchHealth()
    } catch {
      // surface inline in future iteration
    } finally {
      setActionLoading((prev) => ({ ...prev, [itemId]: false }))
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaign Health</h1>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          {lastUpdated && <span>Updated {secondsAgo}s ago</span>}
          <Button variant="outline" size="sm" onClick={fetchHealth} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Summary strip */}
      {health && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <HealthCard
            label="Success rate (24h)"
            value={successRate(health)}
            className={healthColor(health)}
          />
          <HealthCard
            label="Failures (24h)"
            value={String(health.failure_count_24h)}
            className={health.failure_count_24h > 0 ? "text-yellow-600" : "text-green-600"}
          />
          <HealthCard
            label="Dead letters"
            value={String(health.dead_letter_count)}
            className={health.dead_letter_count > 0 ? "text-red-600" : "text-green-600"}
          />
          <HealthCard
            label="Active queue"
            value={String(health.active_count)}
            className="text-foreground"
          />
        </div>
      )}

      {/* Dead-letter table */}
      <section>
        <h2 className="mb-3 text-lg font-medium">Dead-letter queue</h2>
        {deadLetters.length === 0 ? (
          <p className="text-sm text-muted-foreground">No dead-letter items.</p>
        ) : (
          <>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Contact</TableHead>
                    <TableHead>Action type</TableHead>
                    <TableHead>Failure reason</TableHead>
                    <TableHead className="text-right">Retries</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deadLetters.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono text-xs">
                        {item.contact_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{item.action_type}</Badge>
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                        {item.failure_reason ?? "—"}
                      </TableCell>
                      <TableCell className="text-right text-sm">{item.retry_count}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={!item.retry_eligible || actionLoading[item.id]}
                            title={
                              item.retry_eligible
                                ? "Retry this item"
                                : "Max retry count exceeded"
                            }
                            onClick={() => handleRetry(item.id)}
                          >
                            Retry
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={actionLoading[item.id]}
                            onClick={() => handleDismiss(item.id)}
                          >
                            Dismiss
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {/* Simple pagination */}
            <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Showing {(dlPage - 1) * 20 + 1}–{Math.min(dlPage * 20, dlTotal)} of {dlTotal}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={dlPage <= 1}
                  onClick={() => setDlPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={dlPage * 20 >= dlTotal}
                  onClick={() => setDlPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function HealthCard({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${className ?? ""}`}>{value}</p>
    </div>
  )
}
