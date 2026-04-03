import { useEffect, useMemo, useState } from "react"
import { Loader2, Upload } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { engagehubRequest } from "@/lib/engagehub-api"

type CampaignPublic = { id: string; name: string; status: string }

type OfferPackVersionPublic = {
  id: string
  version_number: number
  status: string
  is_default: boolean
  guardrail_compliant: boolean
}

type OfferPackPublic = {
  id: string
  name: string
  current_version: OfferPackVersionPublic | null
}

type OfferPacksPublic = {
  data: OfferPackPublic[]
  count: number
}

type ImportRowError = {
  row_number: number
  column: string
  message: string
}

type CampaignImportPublic = {
  import_id: string
  headers: string[]
  valid_rows: number
  invalid_rows: number
  errors: ImportRowError[]
}

type PreviewRow = { row_number: number; data: Record<string, unknown> }

type ImportPreviewPublic = {
  import_id: string
  preview_rows: PreviewRow[]
  errors: ImportRowError[]
}

const canonicalFields = ["email", "firstName", "company", "timezone"]
const segmentOperators = ["equals", "contains", "startsWith", "in-list"]

const steps = [
  "Campaign basics",
  "CSV upload",
  "Field mapping",
  "Segmentation",
  "Offer/channel strategy",
]

export default function CampaignIntakeWizardPage() {
  const [step, setStep] = useState(0)
  const [campaignName, setCampaignName] = useState("")
  const [campaignId, setCampaignId] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<CampaignImportPublic | null>(null)
  const [preview, setPreview] = useState<ImportPreviewPublic | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [segmentName, setSegmentName] = useState("Default Segment")
  const [segmentField, setSegmentField] = useState("industry")
  const [segmentOperator, setSegmentOperator] = useState("contains")
  const [segmentValue, setSegmentValue] = useState("")
  const [offerPackVersionId, setOfferPackVersionId] = useState("")
  const [assignableOfferPacks, setAssignableOfferPacks] = useState<OfferPackPublic[]>([])
  const [channelStrategy, setChannelStrategy] = useState('{"channel":"email"}')
  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)

  const canMoveForward = useMemo(() => {
    if (step === 0) return campaignName.trim().length > 2
    if (step === 1) return Boolean(file)
    if (step === 2) return importResult !== null
    if (step === 3) return segmentValue.trim().length > 0
    return channelStrategy.trim().length > 1
  }, [step, campaignName, file, importResult, segmentValue, channelStrategy])

  useEffect(() => {
    if (step !== 4 || !campaignId) {
      return
    }

    let cancelled = false
    const loadAssignableOfferPacks = async () => {
      try {
        const response = await engagehubRequest<OfferPacksPublic>("/api/v1/offer-packs/assignable")
        if (!cancelled) {
          setAssignableOfferPacks(response.data)
          if (!offerPackVersionId) {
            const defaultVersion = response.data.find((pack) => pack.current_version?.is_default)?.current_version
            if (defaultVersion) {
              setOfferPackVersionId(defaultVersion.id)
            }
          }
        }
      } catch (error) {
        if (!cancelled) {
          setFeedback(error instanceof Error ? error.message : "Failed to load assignable offer packs")
        }
      }
    }

    void loadAssignableOfferPacks()
    return () => {
      cancelled = true
    }
  }, [campaignId, offerPackVersionId, step])

  const runWithFeedback = async (action: () => Promise<void>) => {
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

  const createCampaign = async () => {
    await runWithFeedback(async () => {
      const campaign = await engagehubRequest<CampaignPublic>("/api/v1/campaigns/", {
        method: "POST",
        idempotent: true,
        body: { name: campaignName.trim() },
      })
      setCampaignId(campaign.id)
      setFeedback(`Campaign draft ${campaign.name} created.`)
      setStep(1)
    })
  }

  const uploadCsv = async () => {
    if (!file || !campaignId) return

    await runWithFeedback(async () => {
      const formData = new FormData()
      formData.append("file", file)
      const result = await engagehubRequest<CampaignImportPublic>(
        `/api/v1/campaigns/${campaignId}/contacts/import`,
        { method: "POST", idempotent: true, formData },
      )

      const draftMapping: Record<string, string> = {}
      for (const field of canonicalFields) {
        draftMapping[field] = result.headers.includes(field) ? field : ""
      }

      setImportResult(result)
      setMapping(draftMapping)
      setFeedback(`Import analyzed: ${result.valid_rows} valid, ${result.invalid_rows} invalid rows.`)
      setStep(2)
    })
  }

  const saveMapping = async () => {
    if (!campaignId) return

    await runWithFeedback(async () => {
      const result = await engagehubRequest<ImportPreviewPublic>(
        `/api/v1/campaigns/${campaignId}/contacts/mapping`,
        {
          method: "POST",
          idempotent: true,
          body: { mapping },
        },
      )
      setPreview(result)
      setFeedback(`Mapping saved. Preview ready for ${result.preview_rows.length} rows.`)
    })
  }

  const saveSegment = async () => {
    if (!campaignId) return

    await runWithFeedback(async () => {
      await engagehubRequest(`/api/v1/campaigns/${campaignId}/segments`, {
        method: "POST",
        idempotent: true,
        body: {
          name: segmentName,
          rules: [
            {
              field_name: segmentField,
              operator: segmentOperator,
              value: segmentValue,
            },
          ],
        },
      })
      setFeedback("Segment saved and estimated count calculated.")
      setStep(4)
    })
  }

  const saveStrategy = async () => {
    if (!campaignId) return

    await runWithFeedback(async () => {
      await engagehubRequest(`/api/v1/campaigns/${campaignId}/strategy`, {
        method: "POST",
        idempotent: true,
        body: {
          offer_pack_version_id: offerPackVersionId || null,
          channel_strategy: JSON.parse(channelStrategy),
        },
      })
      setFeedback("Campaign intake flow complete. Draft strategy saved.")
    })
  }

  const onContinue = async () => {
    if (step === 0) return createCampaign()
    if (step === 1) return uploadCsv()
    if (step === 2) {
      if (!preview) {
        return saveMapping()
      }
      setStep(3)
      return
    }
    if (step === 3) return saveSegment()
    return saveStrategy()
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Campaign intake</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Create campaign drafts, validate CSV uploads, map required fields, define segments,
          and assign channel strategy from a single guided workflow.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Progress</CardTitle>
          <CardDescription>{steps.map((item, index) => `${index + 1}. ${item}`).join("  |  ")}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm">Current step: <strong>{step + 1}. {steps[step]}</strong></p>
        </CardContent>
      </Card>

      {step === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 1: Campaign basics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Label htmlFor="campaignName">Campaign name</Label>
            <Input id="campaignName" value={campaignName} onChange={(event) => setCampaignName(event.target.value)} placeholder="Q2 Product Outreach" />
          </CardContent>
        </Card>
      )}

      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 2: Upload audience CSV</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            <p className="text-xs text-muted-foreground">
              Required canonical fields: {canonicalFields.join(", ")}
            </p>
          </CardContent>
        </Card>
      )}

      {step === 2 && importResult && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Field mapping + preview</CardTitle>
            <CardDescription>
              Map source headers to canonical fields, then validate first 20 resolved rows.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {canonicalFields.map((field) => (
              <div key={field} className="grid grid-cols-2 gap-2">
                <Label>{field}</Label>
                <select
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                  value={mapping[field] || ""}
                  onChange={(event) => setMapping((previous) => ({ ...previous, [field]: event.target.value }))}
                >
                  <option value="">Select source column</option>
                  {importResult.headers.map((header) => (
                    <option key={header} value={header}>{header}</option>
                  ))}
                </select>
              </div>
            ))}

            {preview && (
              <div className="rounded-md border p-3">
                <p className="mb-2 text-sm font-medium">Preview rows</p>
                <div className="space-y-2 text-xs">
                  {preview.preview_rows.slice(0, 20).map((row) => (
                    <pre key={row.row_number} className="rounded bg-muted p-2">{JSON.stringify(row.data, null, 2)}</pre>
                  ))}
                </div>
              </div>
            )}

            {importResult.errors.length > 0 && (
              <div className="rounded-md border border-destructive/40 p-3 text-sm">
                <p className="font-medium text-destructive">Validation issues</p>
                <ul className="list-disc pl-5">
                  {importResult.errors.slice(0, 5).map((error, index) => (
                    <li key={`${error.row_number}-${error.column}-${index}`}>
                      Row {error.row_number}, {error.column}: {error.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 4: Segmentation rule</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            <div>
              <Label htmlFor="segmentName">Segment name</Label>
              <Input id="segmentName" value={segmentName} onChange={(event) => setSegmentName(event.target.value)} />
            </div>
            <div>
              <Label htmlFor="segmentField">Field</Label>
              <Input id="segmentField" value={segmentField} onChange={(event) => setSegmentField(event.target.value)} />
            </div>
            <div>
              <Label htmlFor="segmentOperator">Operator</Label>
              <select
                id="segmentOperator"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={segmentOperator}
                onChange={(event) => setSegmentOperator(event.target.value)}
              >
                {segmentOperators.map((operator) => (
                  <option key={operator} value={operator}>
                    {operator}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="segmentValue">Value</Label>
              <Input id="segmentValue" value={segmentValue} onChange={(event) => setSegmentValue(event.target.value)} />
            </div>
          </CardContent>
        </Card>
      )}

      {step === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 5: Offer/channel strategy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <Label htmlFor="offerPackVersionId">Offer pack version (published)</Label>
              <select
                id="offerPackVersionId"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={offerPackVersionId}
                onChange={(event) => setOfferPackVersionId(event.target.value)}
              >
                <option value="">No offer pack assigned</option>
                {assignableOfferPacks
                  .filter((pack) => pack.current_version)
                  .map((pack) => {
                    const current = pack.current_version
                    if (!current) return null
                    const versionLabel = `v${current.version_number}`
                    const defaultLabel = current.is_default ? " (default)" : ""
                    return (
                      <option key={current.id} value={current.id}>
                        {pack.name} - {versionLabel}{defaultLabel}
                      </option>
                    )
                  })}
              </select>
            </div>
            <div>
              <Label htmlFor="channelStrategy">Channel strategy JSON</Label>
              <Input id="channelStrategy" value={channelStrategy} onChange={(event) => setChannelStrategy(event.target.value)} />
            </div>
          </CardContent>
        </Card>
      )}

      {feedback && (
        <Alert>
          <p className="text-sm">{feedback}</p>
        </Alert>
      )}

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={() => setStep((previous) => Math.max(0, previous - 1))}
          disabled={step === 0 || busy}
        >
          Back
        </Button>
        <Button onClick={onContinue} disabled={!canMoveForward || busy}>
          {busy ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Upload className="mr-2 size-4" />}
          {step === steps.length - 1 ? "Save strategy" : "Continue"}
        </Button>
      </div>
    </div>
  )
}
