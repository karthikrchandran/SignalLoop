import { useEffect, useMemo, useState } from "react"
import { CheckCircle2, Loader2, Mic2, Pencil, Plus, RefreshCw, TriangleAlert, Trash2 } from "lucide-react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { engagehubRequest } from "@/lib/engagehub-api"

type CampaignSummary = {
  id: string
  name: string
}

type CampaignsResponse = {
  data: CampaignSummary[]
}

type ScriptSummary = {
  id: string
  campaign_id: string
  name: string
  active: boolean
  created_at: string
}

type ScriptsResponse = {
  data: ScriptSummary[]
}

type ScriptParsed = {
  opening_pitch: string
  fallback_response: string
  scheduling_question: string
  qa_pairs: Array<{ question: string; answer: string }>
}

type ScriptDetail = ScriptSummary & {
  content: string
  parsed: ScriptParsed | null
}

type SetupIntegration = {
  key: string
  label: string
  configured: boolean
  source: string
  note?: string | null
}

type SetupOverview = {
  callbacks: {
    public_host: boolean
    public_base_url: string
    twilio_twiml_url: string
    twilio_media_stream_url: string
  }
  integrations: SetupIntegration[]
}

const SAMPLE_SCRIPT = [
  "## Opening Pitch",
  "Hi {{first_name}}, this is EngageHub calling about your campaign.",
  "",
  "## Q&A",
  "Q: What does this cover?",
  "A: A brief overview and next steps.",
  "",
  "## Fallback",
  "I can follow up with more detail by email.",
  "",
  "## Scheduling",
  "What time works best for a quick follow-up call?",
].join("\n")

const formatDate = (value: string) => new Date(value).toLocaleString()

export default function VoiceAgentsPage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([])
  const [scripts, setScripts] = useState<ScriptSummary[]>([])
  const [setupOverview, setSetupOverview] = useState<SetupOverview | null>(null)
  const [selectedCampaignId, setSelectedCampaignId] = useState("")
  const [selectedScriptId, setSelectedScriptId] = useState<string | null>(null)
  const [selectedScript, setSelectedScript] = useState<ScriptDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create")
  const [scriptName, setScriptName] = useState("")
  const [editorCampaignId, setEditorCampaignId] = useState("")
  const [scriptContent, setScriptContent] = useState(SAMPLE_SCRIPT)
  const [active, setActive] = useState(true)

  const filteredScripts = useMemo(
    () => scripts.filter((script) => !selectedCampaignId || script.campaign_id === selectedCampaignId),
    [scripts, selectedCampaignId],
  )

  const integrationMap = useMemo(
    () => new Map((setupOverview?.integrations ?? []).map((integration) => [integration.key, integration])),
    [setupOverview],
  )

  const loadIndex = async () => {
    setLoading(true)
    setError(null)
    try {
      const [campaignResponse, scriptsResponse, overviewResponse] = await Promise.all([
        engagehubRequest<CampaignsResponse>("/api/v1/campaigns/"),
        engagehubRequest<ScriptsResponse>("/api/v1/scripts/"),
        engagehubRequest<SetupOverview>("/api/v1/utils/setup-overview/"),
      ])
      setCampaigns(campaignResponse.data)
      setScripts(scriptsResponse.data)
      setSetupOverview(overviewResponse)
      setSelectedCampaignId((current) => current || campaignResponse.data[0]?.id || "")
      setSelectedScriptId((current) => {
        if (current && scriptsResponse.data.some((script) => script.id === current)) {
          return current
        }
        const nextScript = scriptsResponse.data.find(
          (script) => !selectedCampaignId || script.campaign_id === selectedCampaignId,
        )
        return nextScript?.id ?? scriptsResponse.data[0]?.id ?? null
      })
      if (!editorCampaignId && campaignResponse.data[0]) {
        setEditorCampaignId(campaignResponse.data[0].id)
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load voice setup")
    } finally {
      setLoading(false)
    }
  }

  const loadScriptDetail = async (scriptId: string) => {
    try {
      const detail = await engagehubRequest<ScriptDetail>(`/api/v1/scripts/${scriptId}`)
      setSelectedScript(detail)
    } catch (requestError) {
      setSelectedScript(null)
      setError(requestError instanceof Error ? requestError.message : "Failed to load script details")
    }
  }

  useEffect(() => {
    void loadIndex()
  }, [])

  useEffect(() => {
    if (!selectedScriptId) {
      setSelectedScript(null)
      return
    }
    void loadScriptDetail(selectedScriptId)
  }, [selectedScriptId])

  useEffect(() => {
    if (!selectedCampaignId) {
      return
    }
    if (filteredScripts.length === 0) {
      setSelectedScriptId(null)
      return
    }
    if (!selectedScriptId || !filteredScripts.some((script) => script.id === selectedScriptId)) {
      setSelectedScriptId(filteredScripts[0].id)
    }
  }, [filteredScripts, selectedCampaignId, selectedScriptId])

  const openCreateDialog = () => {
    setEditorMode("create")
    setScriptName("")
    setEditorCampaignId(selectedCampaignId || campaigns[0]?.id || "")
    setScriptContent(SAMPLE_SCRIPT)
    setActive(true)
    setDialogOpen(true)
  }

  const openEditDialog = () => {
    if (!selectedScript) {
      return
    }
    setEditorMode("edit")
    setScriptName(selectedScript.name)
    setEditorCampaignId(selectedScript.campaign_id)
    setScriptContent(selectedScript.content)
    setActive(selectedScript.active)
    setDialogOpen(true)
  }

  const saveScript = async () => {
    if (!scriptName.trim() || !editorCampaignId || !scriptContent.trim()) {
      setError("Script name, campaign, and content are required.")
      return
    }

    setSaving(true)
    setError(null)
    setFeedback(null)
    try {
      let scriptId = selectedScript?.id
      if (editorMode === "create") {
        const created = await engagehubRequest<ScriptSummary>("/api/v1/scripts/", {
          method: "POST",
          idempotent: true,
          body: {
            name: scriptName.trim(),
            campaign_id: editorCampaignId,
            content: scriptContent.trim(),
          },
        })
        scriptId = created.id
      } else if (scriptId) {
        await engagehubRequest<ScriptDetail>(`/api/v1/scripts/${scriptId}`, {
          method: "PUT",
          body: {
            name: scriptName.trim(),
            content: scriptContent.trim(),
            active,
          },
        })
      }

      if (!scriptId) {
        throw new Error("Script id was not returned by the API.")
      }

      await loadIndex()
      setSelectedCampaignId(editorCampaignId)
      setSelectedScriptId(scriptId)
      setFeedback(editorMode === "create" ? "Script created." : "Script updated.")
      setDialogOpen(false)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save script")
    } finally {
      setSaving(false)
    }
  }

  const deleteSelectedScript = async () => {
    if (!selectedScript) {
      return
    }
    setSaving(true)
    setError(null)
    setFeedback(null)
    try {
      await engagehubRequest(`/api/v1/scripts/${selectedScript.id}`, {
        method: "DELETE",
      })
      const deletedId = selectedScript.id
      await loadIndex()
      setSelectedScriptId((current) => (current === deletedId ? null : current))
      setSelectedScript(null)
      setFeedback("Script deactivated.")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not deactivate script")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
            <Mic2 className="h-7 w-7 text-primary" />
            Voice Setup
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage real voice scripts, campaign linkage, and provider readiness for AI calling.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void loadIndex()} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh
          </Button>
          <Button onClick={openCreateDialog} disabled={campaigns.length === 0}>
            <Plus className="mr-2 h-4 w-4" />
            New script
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}
      {feedback && <Alert>{feedback}</Alert>}

      <div className="grid gap-4 lg:grid-cols-4">
        <ReadinessCard
          title="Twilio Voice"
          configured={integrationMap.get("twilio")?.configured ?? false}
          source={integrationMap.get("twilio")?.source ?? "missing"}
          detail={integrationMap.get("twilio")?.note ?? "Voice calling, callbacks, and media streams."}
        />
        <ReadinessCard
          title="Deepgram"
          configured={integrationMap.get("deepgram")?.configured ?? false}
          source={integrationMap.get("deepgram")?.source ?? "missing"}
          detail={integrationMap.get("deepgram")?.note ?? "Speech-to-text and text-to-speech for live calls."}
        />
        <ReadinessCard
          title="Groq"
          configured={integrationMap.get("groq")?.configured ?? false}
          source={integrationMap.get("groq")?.source ?? "missing"}
          detail={integrationMap.get("groq")?.note ?? "Live call responses and voice conversation logic."}
        />
        <ReadinessCard
          title="Public callbacks"
          configured={setupOverview?.callbacks.public_host ?? false}
          source={(setupOverview?.callbacks.public_host ?? false) ? "public" : "local"}
          detail={setupOverview?.callbacks.public_host
            ? setupOverview?.callbacks.twilio_twiml_url
            : "Twilio webhooks and media streams still point at a local-only host."}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <Card className="border-border/70">
          <CardHeader>
            <div className="space-y-3">
              <div>
                <CardTitle>Campaign voice scripts</CardTitle>
                <CardDescription>
                  Select a campaign to inspect the real scripts already associated with it.
                </CardDescription>
              </div>
              <div className="space-y-2">
                <Label>Campaign</Label>
                <Select value={selectedCampaignId} onValueChange={setSelectedCampaignId}>
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
          </CardHeader>
          <CardContent className="space-y-3">
            {loading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading voice scripts...
              </div>
            )}

            {!loading && filteredScripts.length === 0 && (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                No scripts found for this campaign. Create one to make the voice path operational.
              </div>
            )}

            {filteredScripts.map((script) => (
              <button
                key={script.id}
                type="button"
                onClick={() => setSelectedScriptId(script.id)}
                className={`w-full rounded-lg border p-4 text-left transition-colors ${
                  selectedScriptId === script.id ? "border-primary bg-primary/5" : "border-border/70 hover:border-primary/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{script.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Created {formatDate(script.created_at)}</p>
                  </div>
                  <Badge variant={script.active ? "default" : "outline"}>{script.active ? "Active" : "Inactive"}</Badge>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>{selectedScript?.name ?? "Script details"}</CardTitle>
                <CardDescription>
                  {selectedScript
                    ? `Campaign: ${campaigns.find((campaign) => campaign.id === selectedScript.campaign_id)?.name ?? "Unknown campaign"}`
                    : "Select a script to see the real parsed preview and campaign association."}
                </CardDescription>
              </div>
              {selectedScript && (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={openEditDialog}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" className="text-rose-500 hover:text-rose-600" onClick={deleteSelectedScript} disabled={saving}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Deactivate
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {!selectedScript && !loading && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                Choose a script to view the backend-parsed preview and voice readiness context.
              </div>
            )}

            {selectedScript && (
              <>
                <div className="grid gap-4 md:grid-cols-3">
                  <MetricCard label="Status" value={selectedScript.active ? "Active" : "Inactive"} />
                  <MetricCard label="Campaign" value={campaigns.find((campaign) => campaign.id === selectedScript.campaign_id)?.name ?? "Unknown"} />
                  <MetricCard label="Created" value={formatDate(selectedScript.created_at)} />
                </div>

                <div className="space-y-3">
                  <div>
                    <h3 className="font-medium">Script source</h3>
                    <p className="text-sm text-muted-foreground">
                      This is the exact backend-backed script content associated with the selected campaign.
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/20 p-4">
                    <pre className="whitespace-pre-wrap text-sm text-foreground">{selectedScript.content}</pre>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <h3 className="font-medium">Parsed preview</h3>
                    <p className="text-sm text-muted-foreground">
                      Derived from the same backend parser used by the script preview endpoint.
                    </p>
                  </div>

                  <PreviewSection title="Opening pitch" content={selectedScript.parsed?.opening_pitch || "Not provided"} />
                  <PreviewSection title="Fallback" content={selectedScript.parsed?.fallback_response || "Not provided"} />
                  <PreviewSection title="Scheduling question" content={selectedScript.parsed?.scheduling_question || "Not provided"} />

                  <div className="rounded-lg border p-4">
                    <p className="font-medium">Q&A pairs</p>
                    <div className="mt-3 space-y-3">
                      {selectedScript.parsed?.qa_pairs?.length ? (
                        selectedScript.parsed.qa_pairs.map((pair, index) => (
                          <div key={`${pair.question}-${index}`} className="rounded-md bg-muted/30 p-3">
                            <p className="text-sm font-medium">Q: {pair.question}</p>
                            <p className="mt-1 text-sm text-muted-foreground">A: {pair.answer}</p>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground">No structured Q&A pairs were parsed from this script.</p>
                      )}
                    </div>
                  </div>
                </div>

                {setupOverview && !setupOverview.callbacks.public_host && (
                  <Alert variant="destructive">
                    Voice scripts are saved, but Twilio callbacks still point at a local host. Update the public callback host in workspace setup before treating voice execution as release-ready.
                  </Alert>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editorMode === "create" ? "Create script" : "Edit script"}</DialogTitle>
            <DialogDescription>
              Save real campaign voice scripts through the backend script CRUD endpoints.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-2">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="script-name">Script name</Label>
                <Input id="script-name" value={scriptName} onChange={(event) => setScriptName(event.target.value)} placeholder="e.g. Discovery call opener" />
              </div>
              <div className="space-y-2">
                <Label>Campaign</Label>
                <Select value={editorCampaignId} onValueChange={setEditorCampaignId}>
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
                <Select value={active ? "active" : "inactive"} onValueChange={(value) => setActive(value === "active")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="script-content">Script content</Label>
              <Textarea
                id="script-content"
                rows={18}
                value={scriptContent}
                onChange={(event) => setScriptContent(event.target.value)}
                placeholder="Paste the script in the backend markdown format"
                className="font-mono"
              />
            </div>

            <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
              Use the backend script format with sections like <strong>Opening Pitch</strong>, <strong>Q&A</strong>, <strong>Fallback</strong>, and <strong>Scheduling</strong>. If the backend rejects the payload, the page keeps the unsaved draft open and surfaces the error instead of pretending it saved.
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={() => void saveScript()} disabled={saving || !scriptName.trim() || !editorCampaignId || !scriptContent.trim()}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editorMode === "create" ? "Create script" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ReadinessCard(props: {
  title: string
  configured: boolean
  source: string
  detail: string
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{props.title}</CardTitle>
            <CardDescription>Source: {props.source}</CardDescription>
          </div>
          <StatusBadge ready={props.configured} />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{props.detail}</p>
      </CardContent>
    </Card>
  )
}

function StatusBadge({ ready }: { ready: boolean }) {
  if (ready) {
    return (
      <Badge className="gap-1">
        <CheckCircle2 className="size-3.5" />
        Ready
      </Badge>
    )
  }

  return (
    <Badge variant="secondary" className="gap-1">
      <TriangleAlert className="size-3.5" />
      Needs setup
    </Badge>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold break-words">{value}</p>
    </div>
  )
}

function PreviewSection({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="font-medium">{title}</p>
      <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{content}</p>
    </div>
  )
}
