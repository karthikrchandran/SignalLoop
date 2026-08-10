import {
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Link2,
  Loader2,
  Phone,
  RefreshCw,
  Send,
  XCircle,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import WorkspaceHeader from "@/components/layout/WorkspaceHeader"
import {
  type SchedulingRequest,
  type SchedulingRequestStatus,
  listSchedulingRequests,
  updateSchedulingRequest,
  withCalendlyState,
} from "./api"

const STATUS_LABELS: Record<SchedulingRequestStatus, string> = {
  pending: "Pending",
  link_sent: "Link Sent",
  booked: "Booked",
  cancelled: "Cancelled",
}

const SOURCE_LABELS: Record<string, string> = {
  voice_call: "Voice Call",
  email_reply: "Email Reply",
  manual: "Manual",
}

const statusVariant = (
  s: SchedulingRequestStatus,
): "default" | "secondary" | "destructive" | "outline" => {
  if (s === "booked") return "default"
  if (s === "link_sent") return "secondary"
  if (s === "cancelled") return "destructive"
  return "outline"
}

const StatusIcon = ({ status }: { status: SchedulingRequestStatus }) => {
  if (status === "booked") return <CheckCircle2 className="size-4 text-green-600" />
  if (status === "link_sent") return <Send className="size-4 text-blue-500" />
  if (status === "cancelled") return <XCircle className="size-4 text-red-500" />
  return <Clock className="size-4 text-amber-500" />
}

function formatDatetime(iso: string | null) {
  if (!iso) return "—"
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso))
}

const ALL_STATUSES: SchedulingRequestStatus[] = [
  "pending",
  "link_sent",
  "booked",
  "cancelled",
]

export default function SchedulingPage() {
  const [requests, setRequests] = useState<SchedulingRequest[]>([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<SchedulingRequestStatus | "all">("all")

  const [selected, setSelected] = useState<SchedulingRequest | null>(null)
  const [linkInput, setLinkInput] = useState("")
  const [notesInput, setNotesInput] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await listSchedulingRequests(
        statusFilter !== "all" ? { status: statusFilter } : undefined,
      )
      setRequests(res.data)
      setCount(res.count)
    } catch {
      setError("Failed to load scheduling requests.")
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    load()
  }, [load])

  function openDialog(req: SchedulingRequest) {
    setSelected(req)
    setLinkInput(req.meeting_link ?? "")
    setNotesInput(req.notes ?? "")
    setSaveError(null)
  }

  async function handleSendLink() {
    if (!selected || !linkInput.trim()) return
    setSaving(true)
    setSaveError(null)
    try {
      const meetingLink = selected.calendly_state
        ? withCalendlyState(linkInput.trim(), selected.calendly_state)
        : linkInput.trim()
      await updateSchedulingRequest(selected.id, { meeting_link: meetingLink })
      setSelected(null)
      await load()
    } catch {
      setSaveError("Failed to send meeting link.")
    } finally {
      setSaving(false)
    }
  }

  async function handleCancel() {
    if (!selected) return
    setSaving(true)
    setSaveError(null)
    try {
      await updateSchedulingRequest(selected.id, { status: "cancelled" })
      setSelected(null)
      await load()
    } catch {
      setSaveError("Failed to cancel request.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        eyebrow="EngageHub"
        title="Meetings & Scheduling"
        description="Contacts who expressed interest in a meeting. Send a booking link or mark as booked once confirmed."
        actions={
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as SchedulingRequestStatus | "all")}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {ALL_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">{count} total</span>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      {loading && requests.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : requests.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No scheduling requests found.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {requests.map((req) => (
            <Card
              key={req.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => openDialog(req)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusIcon status={req.status} />
                    <Badge variant={statusVariant(req.status)}>
                      {STATUS_LABELS[req.status]}
                    </Badge>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {SOURCE_LABELS[req.source] ?? req.source}
                    {req.source === "voice_call" && (
                      <Phone className="ml-1 size-3" />
                    )}
                  </Badge>
                </div>
                <CardDescription className="mt-1 font-mono text-xs">
                  {req.id.slice(0, 8)}…
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                {req.assigned_to_email && (
                  <p className="text-muted-foreground">
                    Assigned: {req.assigned_to_email}
                  </p>
                )}
                {req.meeting_datetime && (
                  <p className="flex items-center gap-1 font-medium text-green-700">
                    <Calendar className="size-3.5" />
                    {formatDatetime(req.meeting_datetime)}
                  </p>
                )}
                {req.meeting_link && (
                  <p className="flex items-center gap-1 text-blue-600 truncate">
                    <Link2 className="size-3.5 shrink-0" />
                    <span className="truncate">{req.meeting_link}</span>
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  Created {formatDatetime(req.created_at)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Detail / action dialog */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Scheduling request</DialogTitle>
            <DialogDescription>
              Source: {selected ? SOURCE_LABELS[selected.source] ?? selected.source : "—"}
              {" · "}
              Status:{" "}
              <Badge
                variant={selected ? statusVariant(selected.status) : "outline"}
              >
                {selected ? STATUS_LABELS[selected.status] : "—"}
              </Badge>
            </DialogDescription>
          </DialogHeader>

          {selected && (
            <div className="space-y-4">
              {selected.meeting_datetime && (
                <div className="rounded-md bg-green-50 p-3 text-sm font-medium text-green-800">
                  <Calendar className="mr-1.5 inline size-4" />
                  Booked for {formatDatetime(selected.meeting_datetime)}
                </div>
              )}

              {selected.status !== "booked" && selected.status !== "cancelled" && (
                <>
                  <div className="space-y-1.5">
                    <Label>Calendly / booking link</Label>
                    <div className="flex gap-2">
                      <Input
                        placeholder="https://calendly.com/your-link"
                        value={linkInput}
                        onChange={(e) => setLinkInput(e.target.value)}
                      />
                      {linkInput && (
                        <Button variant="outline" size="icon" asChild>
                          <a
                            href={
                              selected.calendly_state
                                ? withCalendlyState(linkInput, selected.calendly_state)
                                : linkInput
                            }
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLink className="size-4" />
                          </a>
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      The secure booking state is appended when this link opens so
                      Calendly can confirm only this workspace request.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <Label>Notes</Label>
                    <Textarea
                      rows={3}
                      placeholder="Optional context…"
                      value={notesInput}
                      onChange={(e) => setNotesInput(e.target.value)}
                    />
                  </div>

                  {saveError && (
                    <Alert variant="destructive">{saveError}</Alert>
                  )}
                </>
              )}
            </div>
          )}

          <DialogFooter className="gap-2">
            {selected?.status !== "booked" &&
              selected?.status !== "cancelled" && (
                <>
                  <Button
                    variant="destructive"
                    onClick={handleCancel}
                    disabled={saving}
                  >
                    Cancel request
                  </Button>
                  <Button onClick={handleSendLink} disabled={saving || !linkInput.trim()}>
                    {saving ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 size-4" />
                    )}
                    Send link
                  </Button>
                </>
              )}
            <Button variant="outline" onClick={() => setSelected(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
