import { useEffect, useState } from "react"
import { Loader2, ShieldCheck, Sparkles } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { engagehubRequest } from "@/lib/engagehub-api"

type TemplateVersion = {
  id: string
  version_number: number
  status: "draft" | "published" | "archived"
  guardrail_compliant: boolean
  subject: string | null
  content: string
}

type Template = {
  id: string
  name: string
  channel: string
  current_version: TemplateVersion | null
}

type TemplatesResponse = { data: Template[] }

type PreviewResponse = { rendered_content: string; unresolved_tokens: string[] }

export default function TemplateLibraryPage() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [name, setName] = useState("Welcome Sequence")
  const [channel, setChannel] = useState("email")
  const [subject, setSubject] = useState("Hi {{contact.firstName}}")
  const [content, setContent] = useState("{{contact.firstName}}, here is your offer for {{contact.company}}.")
  const [selectedTemplateId, setSelectedTemplateId] = useState("")
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)

  const loadTemplates = async () => {
    const response = await engagehubRequest<TemplatesResponse>("/api/v1/templates/")
    setTemplates(response.data)
    if (!selectedTemplateId && response.data.length > 0) {
      setSelectedTemplateId(response.data[0].id)
    }
  }

  useEffect(() => {
    loadTemplates().catch((error) => {
      setFeedback(error instanceof Error ? error.message : "Could not load templates")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setFeedback("")
    try {
      await action()
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  const createTemplate = async () => {
    await run(async () => {
      await engagehubRequest("/api/v1/templates/", {
        method: "POST",
        idempotent: true,
        body: {
          name,
          channel,
          subject,
          content,
          tokens: [
            {
              name: "contact.firstName",
              source_field: "contact.firstName",
              default_value: "there",
              fallback_behavior: "defaultValue",
            },
            {
              name: "contact.company",
              source_field: "contact.company",
              default_value: "your company",
              fallback_behavior: "defaultValue",
            },
          ],
        },
      })
      await loadTemplates()
      setFeedback("Template draft created.")
    })
  }

  const previewTemplate = async () => {
    if (!selectedTemplateId) return

    await run(async () => {
      const response = await engagehubRequest<PreviewResponse>(
        `/api/v1/templates/${selectedTemplateId}/preview`,
        {
          method: "POST",
          body: {
            sample_payload: {
              contact: {
                firstName: "Asha",
                company: "Contoso",
              },
            },
          },
        },
      )
      setPreview(response)
      setFeedback("Preview rendered with token substitution.")
    })
  }

  const publishSelected = async () => {
    const selectedTemplate = templates.find((item) => item.id === selectedTemplateId)
    const versionId = selectedTemplate?.current_version?.id
    if (!selectedTemplateId || !versionId) return

    await run(async () => {
      await engagehubRequest(
        `/api/v1/templates/${selectedTemplateId}/versions/${versionId}/publish`,
        {
          method: "POST",
          idempotent: true,
        },
      )
      await loadTemplates()
      setFeedback("Template published after guardrail validation.")
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Template and offer-pack library</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Create versioned templates, validate token behavior, and publish only guardrail-compliant artifacts.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create template draft</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div>
            <Label htmlFor="templateName">Template name</Label>
            <Input id="templateName" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <Label htmlFor="templateChannel">Channel</Label>
            <Input id="templateChannel" value={channel} onChange={(event) => setChannel(event.target.value)} />
          </div>
          <div>
            <Label htmlFor="templateSubject">Subject</Label>
            <Input id="templateSubject" value={subject} onChange={(event) => setSubject(event.target.value)} />
          </div>
          <div>
            <Label htmlFor="templateContent">Body content</Label>
            <Input id="templateContent" value={content} onChange={(event) => setContent(event.target.value)} />
          </div>
          <div className="md:col-span-2">
            <Button onClick={createTemplate} disabled={busy}>
              {busy ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Sparkles className="mr-2 size-4" />}
              Save draft
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Publish readiness</CardTitle>
          <CardDescription>Select a draft, preview token rendering, and publish.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <select
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            value={selectedTemplateId}
            onChange={(event) => setSelectedTemplateId(event.target.value)}
          >
            <option value="">Select template</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name} ({template.current_version?.status || "no version"})
              </option>
            ))}
          </select>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={previewTemplate} disabled={!selectedTemplateId || busy}>
              Preview tokens
            </Button>
            <Button onClick={publishSelected} disabled={!selectedTemplateId || busy}>
              <ShieldCheck className="mr-2 size-4" /> Publish selected
            </Button>
          </div>

          {preview && (
            <div className="rounded-md border p-3 text-sm">
              <p className="font-medium">Rendered preview</p>
              <p className="mt-1">{preview.rendered_content}</p>
              {preview.unresolved_tokens.length > 0 && (
                <p className="mt-2 text-destructive">
                  Unresolved tokens: {preview.unresolved_tokens.join(", ")}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Published artifacts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {templates.filter((template) => template.current_version?.status === "published").map((template) => (
            <div key={template.id} className="rounded border p-2">
              <p className="font-medium">{template.name}</p>
              <p className="text-muted-foreground">
                Version {template.current_version?.version_number} • Guardrail compliant: {String(template.current_version?.guardrail_compliant)}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      {feedback && (
        <Alert>
          <p className="text-sm">{feedback}</p>
        </Alert>
      )}
    </div>
  )
}
