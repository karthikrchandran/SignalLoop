import { useEffect, useState } from "react"
import { Copy, FileText, Loader2, ShieldCheck, Sparkles } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { signalloopRequest } from "@/lib/signalloop-api"

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

// ── Starter templates ────────────────────────────────────────────────────────
const STARTER_TEMPLATES = [
  {
    id: "starter-welcome",
    name: "Welcome to the Family",
    channel: "email",
    tag: "Onboarding",
    subject: "Welcome, {{contact.firstName}}! Let's get started 🎉",
    content:
      `Hi {{contact.firstName}},\n\nWe're thrilled to have you on board at {{company.name}}. Over the next few days, we'll share tips to help you get the most out of your experience.\n\nIn the meantime, if you have any questions, just reply to this email — we're always happy to help.\n\nWarm regards,\n{{sender.name}}\n{{company.name}}`,
  },
  {
    id: "starter-offer",
    name: "Your Exclusive Offer Awaits",
    channel: "email",
    tag: "Promotional",
    subject: "{{contact.firstName}}, your exclusive deal expires soon",
    content:
      `Hi {{contact.firstName}},\n\nWe have a special offer reserved just for you — but it expires on {{offer.expiryDate}}.\n\n{{offer.headline}}: {{offer.details}}\n\nClaim your offer here: {{offer.ctaUrl}}\n\nDon't miss out!\n\n{{sender.name}}\n{{company.name}}`,
  },
  {
    id: "starter-reengagement",
    name: "We Miss You",
    channel: "email",
    tag: "Re-engagement",
    subject: "{{contact.firstName}}, it's been a while — let's reconnect",
    content:
      `Hi {{contact.firstName}},\n\nWe noticed we haven't heard from you in a while, and we've missed you!\n\nA lot has happened since your last visit — {{company.latestUpdate}}. We think you'll love what we've been building.\n\nClick below to see what's new:\n{{campaign.ctaUrl}}\n\nWe hope to see you soon,\n{{sender.name}}`,
  },
  {
    id: "starter-reminder",
    name: "Appointment Reminder",
    channel: "email",
    tag: "Transactional",
    subject: "Reminder: Your appointment on {{appointment.date}}",
    content:
      `Hi {{contact.firstName}},\n\nThis is a friendly reminder about your upcoming appointment:\n\nDate: {{appointment.date}}\nTime: {{appointment.time}}\nLocation: {{appointment.location}}\n\nIf you need to reschedule, please reply to this email or call us at {{company.phone}}.\n\nSee you soon!\n{{sender.name}}`,
  },
  {
    id: "starter-thankyou",
    name: "Thank You for Your Business",
    channel: "email",
    tag: "Post-purchase",
    subject: "Thank you, {{contact.firstName}} — we appreciate your business",
    content:
      `Hi {{contact.firstName}},\n\nThank you for choosing {{company.name}}! Your order {{order.id}} has been confirmed.\n\nHere's a summary:\n{{order.summary}}\n\nIf you have any questions, we're here to help.\n\nWith gratitude,\n{{sender.name}}\n{{company.name}}`,
  },
]
// ─────────────────────────────────────────────────────────────────────────────

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
    const response = await signalloopRequest<TemplatesResponse>("/api/v1/templates/")
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
      await signalloopRequest("/api/v1/templates/", {
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
      const response = await signalloopRequest<PreviewResponse>(
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
      await signalloopRequest(
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
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <FileText className="h-7 w-7 text-primary" />
          Template Library
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Start from a prebuilt starter template or create your own. Preview token
          rendering, then publish when ready.
        </p>
      </div>

      {/* ── Starter templates ─────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Starter Templates</CardTitle>
          <CardDescription>
            Ready-to-use templates for common outreach scenarios. Click{" "}
            <strong>Use Template</strong> to pre-fill the editor below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {STARTER_TEMPLATES.map((tmpl) => (
              <div
                key={tmpl.id}
                className="rounded-lg border border-border/70 p-4 flex flex-col gap-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-sm">{tmpl.name}</p>
                  <Badge variant="secondary" className="text-xs shrink-0">{tmpl.tag}</Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">{tmpl.subject}</p>
                <div className="flex gap-2 mt-auto pt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1 flex-1"
                    onClick={() => {
                      setName(tmpl.name)
                      setChannel(tmpl.channel)
                      setSubject(tmpl.subject)
                      setContent(tmpl.content)
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Use Template
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Create draft ──────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Create Template Draft</CardTitle>
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

      {/* ── Publish readiness ─────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Publish Readiness</CardTitle>
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

      {/* ── Published artifacts ───────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Published Templates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {templates.filter((template) => template.current_version?.status === "published").map((template) => (
            <div key={template.id} className="rounded border p-2">
              <p className="font-medium">{template.name}</p>
              <p className="text-muted-foreground">
                Version {template.current_version?.version_number} · Guardrail compliant:{" "}
                {String(template.current_version?.guardrail_compliant)}
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
