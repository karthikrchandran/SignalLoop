import { useEffect, useState } from "react"
import { Boxes } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { engagehubRequest } from "@/lib/engagehub-api"

type OfferPackVersion = {
  id: string
  status: string
  version_number: number
  is_default: boolean
  guardrail_compliant: boolean
}

type OfferPack = {
  id: string
  name: string
  current_version: OfferPackVersion | null
}

type OfferPackResponse = { data: OfferPack[] }

type Template = { id: string; name: string; channel: string; current_version: { id: string; status: string } | null }

type TemplateResponse = { data: Template[] }

export default function OfferPackLibraryPage() {
  const [offerPacks, setOfferPacks] = useState<OfferPack[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [name, setName] = useState("Starter offer pack")
  const [templateVersionId, setTemplateVersionId] = useState("")
  const [channel, setChannel] = useState("email")
  const [isDefault, setIsDefault] = useState(false)
  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)

  const loadData = async () => {
    const [offerPackResult, templateResult] = await Promise.all([
      engagehubRequest<OfferPackResponse>("/api/v1/offer-packs/"),
      engagehubRequest<TemplateResponse>("/api/v1/templates/?status=published"),
    ])
    setOfferPacks(offerPackResult.data)
    setTemplates(templateResult.data)
    if (!templateVersionId && templateResult.data[0]?.current_version?.id) {
      setTemplateVersionId(templateResult.data[0].current_version.id)
    }
  }

  useEffect(() => {
    loadData().catch((error) => {
      setFeedback(error instanceof Error ? error.message : "Failed to load offer-pack context")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const createOfferPack = async () => {
    if (!templateVersionId) {
      setFeedback("Publish at least one template version before creating an offer pack.")
      return
    }

    setBusy(true)
    setFeedback("")
    try {
      await engagehubRequest("/api/v1/offer-packs/", {
        method: "POST",
        idempotent: true,
        body: {
          name,
          is_default: isDefault,
          bindings: [
            {
              template_version_id: templateVersionId,
              channel,
              script_variant: "default",
            },
          ],
        },
      })
      await loadData()
      setFeedback("Offer pack version created and published.")
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Offer packs</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Compose reusable offer bundles from published template versions and promote a default pack per workspace.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create published offer-pack version</CardTitle>
          <CardDescription>Only published and compliant template versions can be bound.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div>
            <Label htmlFor="offerPackName">Offer pack name</Label>
            <Input id="offerPackName" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <Label htmlFor="offerPackTemplateVersion">Template version</Label>
            <select
              id="offerPackTemplateVersion"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={templateVersionId}
              onChange={(event) => setTemplateVersionId(event.target.value)}
            >
              <option value="">Select published template version</option>
              {templates
                .filter((template) => template.current_version?.status === "published")
                .map((template) => (
                  <option key={template.id} value={template.current_version?.id || ""}>
                    {template.name} ({template.channel})
                  </option>
                ))}
            </select>
          </div>
          <div>
            <Label htmlFor="offerPackChannel">Channel</Label>
            <Input id="offerPackChannel" value={channel} onChange={(event) => setChannel(event.target.value)} />
          </div>
          <div className="flex items-center gap-2 pt-6">
            <input
              id="offerPackDefault"
              type="checkbox"
              checked={isDefault}
              onChange={(event) => setIsDefault(event.target.checked)}
            />
            <Label htmlFor="offerPackDefault">Set as default version</Label>
          </div>
          <div className="md:col-span-2">
            <Button onClick={createOfferPack} disabled={busy}>
              <Boxes className="mr-2 size-4" /> Create offer pack
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Published offer packs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {offerPacks.map((offerPack) => (
            <div key={offerPack.id} className="rounded border p-2">
              <p className="font-medium">{offerPack.name}</p>
              <p className="text-muted-foreground">
                Version {offerPack.current_version?.version_number || 0} • Status {offerPack.current_version?.status || "unknown"} • Default {String(offerPack.current_version?.is_default)}
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
