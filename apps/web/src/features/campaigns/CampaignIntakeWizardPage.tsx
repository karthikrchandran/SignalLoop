import { useEffect, useMemo, useState } from "react"
import { CheckCircle2, Loader2, Search, Users } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { signalloopRequest } from "@/lib/signalloop-api"

type CampaignPublic = { id: string; name: string; status: string }

type Contact = {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  company: string | null
  phone: string | null
  timezone: string
}

type ContactsResponse = { data: Contact[]; count: number }

type CampaignAudiencePublic = {
  campaign_id: string
  selected_count: number
  added_count: number
  existing_count: number
  segment_id: string | null
  segment_name: string | null
}

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

const audienceModes = [
  { value: "all", label: "All contacts" },
  { value: "selected", label: "Selected contacts" },
  { value: "filtered", label: "Filtered subset" },
] as const

type AudienceMode = (typeof audienceModes)[number]["value"]

const filterFields = ["email", "firstName", "lastName", "company", "phone", "timezone"]
const segmentOperators = ["equals", "contains", "startsWith", "in-list"]

const steps = ["Campaign basics", "Audience selection", "Offer/channel strategy"]

function contactName(contact: Contact) {
  return [contact.first_name, contact.last_name].filter(Boolean).join(" ") || "-"
}

export default function CampaignIntakeWizardPage() {
  const [step, setStep] = useState(0)
  const [campaignName, setCampaignName] = useState("")
  const [campaignId, setCampaignId] = useState("")
  const [contacts, setContacts] = useState<Contact[]>([])
  const [contactCount, setContactCount] = useState(0)
  const [contactSearch, setContactSearch] = useState("")
  const [audienceMode, setAudienceMode] = useState<AudienceMode>("all")
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [segmentName, setSegmentName] = useState("Campaign audience")
  const [segmentField, setSegmentField] = useState("company")
  const [segmentOperator, setSegmentOperator] = useState("contains")
  const [segmentValue, setSegmentValue] = useState("")
  const [audienceResult, setAudienceResult] = useState<CampaignAudiencePublic | null>(null)
  const [offerPackVersionId, setOfferPackVersionId] = useState("")
  const [assignableOfferPacks, setAssignableOfferPacks] = useState<OfferPackPublic[]>([])
  const [channelStrategy, setChannelStrategy] = useState('{"channel":"email"}')
  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)
  const [loadingContacts, setLoadingContacts] = useState(false)

  const canMoveForward = useMemo(() => {
    if (step === 0) return campaignName.trim().length > 2
    if (step === 1) {
      if (audienceMode === "all") return contactCount > 0
      if (audienceMode === "selected") return selectedContactIds.length > 0
      return segmentValue.trim().length > 0
    }
    return channelStrategy.trim().length > 1
  }, [step, campaignName, audienceMode, contactCount, selectedContactIds.length, segmentValue, channelStrategy])

  async function loadContacts(nextSearch = contactSearch) {
    setLoadingContacts(true)
    try {
      const params = new URLSearchParams()
      if (nextSearch.trim()) params.set("search", nextSearch.trim())
      const response = await signalloopRequest<ContactsResponse>(`/api/v1/contacts/?${params.toString()}`)
      setContacts(response.data)
      setContactCount(response.count)
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Failed to load contacts")
    } finally {
      setLoadingContacts(false)
    }
  }

  useEffect(() => {
    if (step === 1) {
      void loadContacts("")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

  useEffect(() => {
    if (step !== 2 || !campaignId) {
      return
    }

    let cancelled = false
    const loadAssignableOfferPacks = async () => {
      try {
        const response = await signalloopRequest<OfferPacksPublic>("/api/v1/offer-packs/assignable")
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
      const campaign = await signalloopRequest<CampaignPublic>("/api/v1/campaigns/", {
        method: "POST",
        body: { name: campaignName.trim() },
      })
      setCampaignId(campaign.id)
      setFeedback(`Campaign draft ${campaign.name} created.`)
      setStep(1)
    })
  }

  const saveAudience = async () => {
    if (!campaignId) return

    await runWithFeedback(async () => {
      const rules = audienceMode === "filtered"
        ? [{ field_name: segmentField, operator: segmentOperator, value: segmentValue }]
        : []
      const result = await signalloopRequest<CampaignAudiencePublic>(
        `/api/v1/campaigns/${campaignId}/audience`,
        {
          method: "POST",
          body: {
            include_all_contacts: audienceMode === "all",
            contact_ids: audienceMode === "selected" ? selectedContactIds : [],
            segment_name: audienceMode === "all" ? null : segmentName.trim() || null,
            rules,
          },
        },
      )
      setAudienceResult(result)
      setFeedback(`Audience ready: ${result.selected_count} selected, ${result.added_count} newly assigned.`)
      setStep(2)
    })
  }

  const saveStrategy = async () => {
    if (!campaignId) return

    await runWithFeedback(async () => {
      await signalloopRequest(`/api/v1/campaigns/${campaignId}/strategy`, {
        method: "POST",
        body: {
          offer_pack_version_id: offerPackVersionId || null,
          channel_strategy: JSON.parse(channelStrategy),
        },
      })
      setFeedback("Campaign intake flow complete. Draft audience and strategy saved.")
    })
  }

  const onContinue = async () => {
    if (step === 0) return createCampaign()
    if (step === 1) return saveAudience()
    return saveStrategy()
  }

  function toggleContact(contactId: string, checked: boolean) {
    setSelectedContactIds((current) =>
      checked
        ? Array.from(new Set([...current, contactId]))
        : current.filter((id) => id !== contactId),
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Campaign intake</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Create a campaign draft, choose leads from the contact pool, and assign channel strategy.
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
            <CardTitle>Step 2: Audience selection</CardTitle>
            <CardDescription>{contactCount} available contact{contactCount === 1 ? "" : "s"}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-3 md:grid-cols-3">
              {audienceModes.map((mode) => (
                <label
                  key={mode.value}
                  className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${audienceMode === mode.value ? "border-primary bg-primary/5" : ""}`}
                >
                  <input
                    type="radio"
                    name="audienceMode"
                    value={mode.value}
                    checked={audienceMode === mode.value}
                    onChange={() => setAudienceMode(mode.value)}
                  />
                  {mode.label}
                </label>
              ))}
            </div>

            {audienceMode !== "all" && (
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label htmlFor="segmentName">Subset name</Label>
                  <Input id="segmentName" value={segmentName} onChange={(event) => setSegmentName(event.target.value)} />
                </div>
                {audienceMode === "filtered" && (
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label htmlFor="segmentField">Field</Label>
                      <select
                        id="segmentField"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                        value={segmentField}
                        onChange={(event) => setSegmentField(event.target.value)}
                      >
                        {filterFields.map((field) => <option key={field} value={field}>{field}</option>)}
                      </select>
                    </div>
                    <div>
                      <Label htmlFor="segmentOperator">Operator</Label>
                      <select
                        id="segmentOperator"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                        value={segmentOperator}
                        onChange={(event) => setSegmentOperator(event.target.value)}
                      >
                        {segmentOperators.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
                      </select>
                    </div>
                    <div>
                      <Label htmlFor="segmentValue">Value</Label>
                      <Input id="segmentValue" value={segmentValue} onChange={(event) => setSegmentValue(event.target.value)} />
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <div className="relative min-w-72 flex-1">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={contactSearch}
                  onChange={(event) => setContactSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void loadContacts(contactSearch)
                  }}
                  className="pl-9"
                  placeholder="Search lead pool"
                />
              </div>
              <Button variant="outline" onClick={() => void loadContacts(contactSearch)} disabled={loadingContacts}>
                {loadingContacts ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Search className="mr-2 size-4" />}
                Search
              </Button>
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  {audienceMode === "selected" && <TableHead className="w-12">Pick</TableHead>}
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Timezone</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contacts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={audienceMode === "selected" ? 6 : 5} className="py-10 text-center text-muted-foreground">
                      No contacts found.
                    </TableCell>
                  </TableRow>
                ) : (
                  contacts.map((contact) => (
                    <TableRow key={contact.id}>
                      {audienceMode === "selected" && (
                        <TableCell>
                          <Checkbox
                            checked={selectedContactIds.includes(contact.id)}
                            onCheckedChange={(checked) => toggleContact(contact.id, checked === true)}
                          />
                        </TableCell>
                      )}
                      <TableCell className="font-medium">{contact.email}</TableCell>
                      <TableCell>{contactName(contact)}</TableCell>
                      <TableCell>{contact.company || "-"}</TableCell>
                      <TableCell>{contact.phone || <Badge variant="outline">No phone</Badge>}</TableCell>
                      <TableCell>{contact.timezone || "UTC"}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Offer/channel strategy</CardTitle>
            {audienceResult && (
              <CardDescription>{audienceResult.selected_count} contacts assigned to this campaign</CardDescription>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <Label htmlFor="offerPackVersionId">Offer pack version</Label>
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
          {busy ? <Loader2 className="mr-2 size-4 animate-spin" /> : step === 1 ? <Users className="mr-2 size-4" /> : <CheckCircle2 className="mr-2 size-4" />}
          {step === steps.length - 1 ? "Save strategy" : "Continue"}
        </Button>
      </div>
    </div>
  )
}
