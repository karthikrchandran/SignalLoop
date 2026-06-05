import { useEffect, useState } from "react"
import { ListOrdered, Loader2, Pencil, Plus, RefreshCw, Trash2, Users } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { engagehubRequest } from "@/lib/engagehub-api"

type CampaignSummary = {
  id: string
  name: string
}

type SequenceSummary = {
  id: string
  campaign_id: string
  name: string
  active: boolean
  created_at: string
}

type SequenceStep = {
  id: string
  step_order: number
  delay_days: number
  subject_template: string
  body_template: string
}

type SequenceDetail = SequenceSummary & {
  steps: SequenceStep[]
}

type SequencesResponse = {
  data: SequenceSummary[]
}

type CampaignsResponse = {
  data: CampaignSummary[]
}

type SequenceProgress = {
  total_enrolled: number
  status_breakdown: Record<string, number>
}

type EditableStep = {
  localId: string
  delay_days: number
  subject_template: string
  body_template: string
}

const TOKEN_LABELS = ["first_name", "last_name", "email", "company", "phone"]

const createEditableStep = (step?: SequenceStep): EditableStep => ({
  localId: crypto.randomUUID(),
  delay_days: step?.delay_days ?? 0,
  subject_template: step?.subject_template ?? "",
  body_template: step?.body_template ?? "",
})

const statusVariant = (active: boolean): "default" | "outline" => (active ? "default" : "outline")

const formatStatusLabel = (active: boolean) => (active ? "Active" : "Draft")

const formatDate = (value: string) => new Date(value).toLocaleString()

const formatCampaignName = (campaignId: string, campaigns: CampaignSummary[]) => {
  return campaigns.find((campaign) => campaign.id === campaignId)?.name ?? "Unknown campaign"
}

export default function SequencesPage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([])
  const [sequences, setSequences] = useState<SequenceSummary[]>([])
  const [selectedSequenceId, setSelectedSequenceId] = useState<string | null>(null)
  const [selectedSequence, setSelectedSequence] = useState<SequenceDetail | null>(null)
  const [selectedProgress, setSelectedProgress] = useState<SequenceProgress | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [enrolling, setEnrolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create")
  const [sequenceName, setSequenceName] = useState("")
  const [campaignId, setCampaignId] = useState("")
  const [active, setActive] = useState(false)
  const [steps, setSteps] = useState<EditableStep[]>([createEditableStep()])

  const loadIndex = async () => {
    setLoading(true)
    setError(null)
    try {
      const [campaignResponse, sequenceResponse] = await Promise.all([
        engagehubRequest<CampaignsResponse>("/api/v1/campaigns/"),
        engagehubRequest<SequencesResponse>("/api/v1/sequences/"),
      ])
      setCampaigns(campaignResponse.data)
      setSequences(sequenceResponse.data)
      setSelectedSequenceId((current) => {
        if (current && sequenceResponse.data.some((sequence) => sequence.id === current)) {
          return current
        }
        return sequenceResponse.data[0]?.id ?? null
      })
      if (!campaignId && campaignResponse.data[0]) {
        setCampaignId(campaignResponse.data[0].id)
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load sequences")
    } finally {
      setLoading(false)
    }
  }

  const loadSelectedSequence = async (sequenceId: string) => {
    try {
      const [detail, progress] = await Promise.all([
        engagehubRequest<SequenceDetail>(`/api/v1/sequences/${sequenceId}`),
        engagehubRequest<SequenceProgress>(`/api/v1/sequences/${sequenceId}/progress`),
      ])
      setSelectedSequence(detail)
      setSelectedProgress(progress)
    } catch (requestError) {
      setSelectedSequence(null)
      setSelectedProgress(null)
      setError(requestError instanceof Error ? requestError.message : "Failed to load sequence details")
    }
  }

  useEffect(() => {
    void loadIndex()
  }, [])

  useEffect(() => {
    if (!selectedSequenceId) {
      setSelectedSequence(null)
      setSelectedProgress(null)
      return
    }
    void loadSelectedSequence(selectedSequenceId)
  }, [selectedSequenceId])

  const openCreateDialog = () => {
    setEditorMode("create")
    setSequenceName("")
    setActive(false)
    setSteps([createEditableStep()])
    setCampaignId((current) => current || campaigns[0]?.id || "")
    setDialogOpen(true)
  }

  const openEditDialog = () => {
    if (!selectedSequence) {
      return
    }
    setEditorMode("edit")
    setSequenceName(selectedSequence.name)
    setCampaignId(selectedSequence.campaign_id)
    setActive(selectedSequence.active)
    setSteps(
      selectedSequence.steps.length > 0
        ? selectedSequence.steps.map((step) => createEditableStep(step))
        : [createEditableStep()],
    )
    setDialogOpen(true)
  }

  const updateStep = (localId: string, patch: Partial<EditableStep>) => {
    setSteps((current) => current.map((step) => (step.localId === localId ? { ...step, ...patch } : step)))
  }

  const addStep = () => {
    setSteps((current) => [...current, createEditableStep()])
  }

  const removeStep = (localId: string) => {
    setSteps((current) => (current.length > 1 ? current.filter((step) => step.localId !== localId) : current))
  }

  const saveSequence = async () => {
    if (!sequenceName.trim() || !campaignId) {
      setError("Sequence name and campaign are required.")
      return
    }

    const normalizedSteps = steps.map((step, index) => ({
      step_order: index + 1,
      delay_days: Math.max(0, Number(step.delay_days) || 0),
      subject_template: step.subject_template.trim(),
      body_template: step.body_template.trim(),
    }))

    if (normalizedSteps.some((step) => !step.subject_template || !step.body_template)) {
      setError("Each sequence step needs both a subject and a body.")
      return
    }

    setSaving(true)
    setError(null)
    setFeedback(null)
    try {
      let sequenceId = selectedSequence?.id
      if (editorMode === "create") {
        const created = await engagehubRequest<SequenceSummary>("/api/v1/sequences/", {
          method: "POST",
          idempotent: true,
          body: {
            name: sequenceName.trim(),
            campaign_id: campaignId,
          },
        })
        sequenceId = created.id
      } else if (sequenceId) {
        await engagehubRequest<SequenceSummary>(`/api/v1/sequences/${sequenceId}`, {
          method: "PUT",
          body: {
            name: sequenceName.trim(),
            active,
          },
        })
      }

      if (!sequenceId) {
        throw new Error("Sequence id was not returned by the API.")
      }

      await engagehubRequest<SequenceDetail>(`/api/v1/sequences/${sequenceId}/steps`, {
        method: "PUT",
        body: { steps: normalizedSteps },
      })

      await loadIndex()
      setSelectedSequenceId(sequenceId)
      setFeedback(editorMode === "create" ? "Sequence created." : "Sequence updated.")
      setDialogOpen(false)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save sequence")
    } finally {
      setSaving(false)
    }
  }

  const deleteSelectedSequence = async () => {
    if (!selectedSequence) {
      return
    }
    setSaving(true)
    setError(null)
    setFeedback(null)
    try {
      await engagehubRequest(`/api/v1/sequences/${selectedSequence.id}`, {
        method: "DELETE",
      })
      const deletedId = selectedSequence.id
      await loadIndex()
      setSelectedSequenceId((current) => (current === deletedId ? null : current))
      setSelectedSequence(null)
      setSelectedProgress(null)
      setFeedback("Sequence deleted.")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete sequence")
    } finally {
      setSaving(false)
    }
  }

  const enrollSelectedSequence = async () => {
    if (!selectedSequence) {
      return
    }
    setEnrolling(true)
    setError(null)
    setFeedback(null)
    try {
      const result = await engagehubRequest<{ enrolled: number; message: string }>(
        `/api/v1/sequences/${selectedSequence.id}/enroll/${selectedSequence.campaign_id}`,
        {
          method: "POST",
        },
      )
      await loadSelectedSequence(selectedSequence.id)
      setFeedback(result.message)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not enroll contacts")
    } finally {
      setEnrolling(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
            <ListOrdered className="h-7 w-7 text-primary" />
            Sequences
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage live multi-step outreach flows against the backend sequence service.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void loadIndex()} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh
          </Button>
          <Button className="gap-2" onClick={openCreateDialog} disabled={campaigns.length === 0}>
            <Plus className="h-4 w-4" />
            New Sequence
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}
      {feedback && <Alert>{feedback}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <Card className="border-border/70">
          <CardHeader>
            <CardTitle>Real sequences</CardTitle>
            <CardDescription>
              Loaded from the backend. Select a sequence to inspect, edit, or enroll campaign contacts.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading sequences...
              </div>
            )}

            {!loading && sequences.length === 0 && (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                No sequences exist yet for this workspace. Create one to start wiring campaign outreach.
              </div>
            )}

            {sequences.map((sequence) => (
              <button
                key={sequence.id}
                type="button"
                onClick={() => setSelectedSequenceId(sequence.id)}
                className={`w-full rounded-lg border p-4 text-left transition-colors ${
                  selectedSequenceId === sequence.id ? "border-primary bg-primary/5" : "border-border/70 hover:border-primary/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{sequence.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatCampaignName(sequence.campaign_id, campaigns)}
                    </p>
                  </div>
                  <Badge variant={statusVariant(sequence.active)}>{formatStatusLabel(sequence.active)}</Badge>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">Created {formatDate(sequence.created_at)}</p>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>{selectedSequence?.name ?? "Sequence details"}</CardTitle>
                <CardDescription>
                  {selectedSequence
                    ? `Campaign: ${formatCampaignName(selectedSequence.campaign_id, campaigns)}`
                    : "Select a sequence to view backend-backed steps and enrollment progress."}
                </CardDescription>
              </div>
              {selectedSequence && (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={openEditDialog}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={enrollSelectedSequence} disabled={enrolling}>
                    {enrolling ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Users className="mr-2 h-4 w-4" />}
                    Enroll contacts
                  </Button>
                  <Button size="sm" variant="ghost" className="text-rose-500 hover:text-rose-600" onClick={deleteSelectedSequence} disabled={saving}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {!selectedSequence && !loading && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                Choose a sequence from the list to inspect its real step content and campaign enrollment status.
              </div>
            )}

            {selectedSequence && (
              <>
                <div className="grid gap-4 md:grid-cols-3">
                  <MetricCard label="Status" value={formatStatusLabel(selectedSequence.active)} />
                  <MetricCard label="Total enrolled" value={String(selectedProgress?.total_enrolled ?? 0)} />
                  <MetricCard label="Steps" value={String(selectedSequence.steps.length)} />
                </div>

                <div>
                  <div className="mb-2 flex items-center gap-2">
                    <h3 className="font-medium">Step preview</h3>
                    <Badge variant="outline">Backend data</Badge>
                  </div>
                  <div className="space-y-3">
                    {selectedSequence.steps.map((step) => (
                      <div key={step.id} className="rounded-lg border p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-medium">Step {step.step_order}</p>
                          <span className="text-xs text-muted-foreground">Delay: {step.delay_days} day(s)</span>
                        </div>
                        <p className="mt-3 text-sm font-medium">{step.subject_template}</p>
                        <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{step.body_template}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <h3 className="font-medium">Supported personalization tokens</h3>
                    <p className="text-sm text-muted-foreground">
                      These tokens match the current backend sequence rendering support.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {TOKEN_LABELS.map((token) => (
                      <Badge key={token} variant="secondary">{`{{${token}}}`}</Badge>
                    ))}
                  </div>
                </div>

                {selectedProgress && (
                  <div className="space-y-3">
                    <div>
                      <h3 className="font-medium">Enrollment status</h3>
                      <p className="text-sm text-muted-foreground">
                        Live backend progress for the selected sequence.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(selectedProgress.status_breakdown).map(([status, count]) => (
                        <Badge key={status} variant="outline">{`${status}: ${count}`}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editorMode === "create" ? "Create sequence" : "Edit sequence"}</DialogTitle>
            <DialogDescription>
              Persist the sequence against the real API, including ordered steps and campaign linkage.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-2">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="sequence-name">Sequence name</Label>
                <Input id="sequence-name" value={sequenceName} onChange={(event) => setSequenceName(event.target.value)} placeholder="e.g. Spring launch outreach" />
              </div>
              <div className="space-y-2">
                <Label>Campaign</Label>
                <Select value={campaignId} onValueChange={setCampaignId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select campaign" />
                  </SelectTrigger>
                  <SelectContent>
                    {campaigns.map((campaign) => (
                      <SelectItem key={campaign.id} value={campaign.id}>{campaign.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {editorMode === "edit" && (
              <div className="space-y-2">
                <Label>Status</Label>
                <Select value={active ? "active" : "draft"} onValueChange={(value) => setActive(value === "active")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-medium">Steps</h3>
                  <p className="text-sm text-muted-foreground">These are saved through the real batch step upsert endpoint.</p>
                </div>
                <Button type="button" variant="outline" onClick={addStep}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add step
                </Button>
              </div>

              {steps.map((step, index) => (
                <div key={step.localId} className="rounded-lg border p-4 space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">Step {index + 1}</p>
                    <Button type="button" variant="ghost" onClick={() => removeStep(step.localId)} disabled={steps.length === 1}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Remove
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <Label>Delay in days</Label>
                    <Input
                      type="number"
                      min={0}
                      value={step.delay_days}
                      onChange={(event) => updateStep(step.localId, { delay_days: Number(event.target.value) })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Subject template</Label>
                    <Input
                      value={step.subject_template}
                      onChange={(event) => updateStep(step.localId, { subject_template: event.target.value })}
                      placeholder="Subject line"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Body template</Label>
                    <Textarea
                      value={step.body_template}
                      onChange={(event) => updateStep(step.localId, { body_template: event.target.value })}
                      placeholder="Email body"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={() => void saveSequence()} disabled={saving || !campaignId || !sequenceName.trim()}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editorMode === "create" ? "Create sequence" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  )
}
