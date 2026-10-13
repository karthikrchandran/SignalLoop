import {
  Bot,
  Building2,
  CheckCircle2,
  Clock3,
  Compass,
  Copy,
  Flame,
  Globe,
  Layers,
  Loader2,
  Mail,
  MessageSquare,
  Phone,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  UserCheck,
  Users,
  Zap,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { WorkspacePage } from "@/components/workspace/WorkspacePage"
import {
  enrollProspects,
  listProspectingCampaigns,
  listProspectingResearch,
  listProspectingSequences,
  listReadyContacts,
  type ProspectingCampaign,
  type ProspectingPriority,
  type ProspectingReadyContact,
  type ProspectingResearchResult,
  type ProspectingSequence,
  runBulkProspectingResearch,
  runProspectingResearch,
} from "@/features/prospecting/api"

function contactLabel(contact: ProspectingReadyContact) {
  const name = [contact.first_name, contact.last_name].filter(Boolean).join(" ")
  const company = contact.company ? ` - ${contact.company}` : ""
  return `${name || contact.email}${company}`
}

function priorityLabel(priority: ProspectingPriority) {
  return `${priority[0].toUpperCase()}${priority.slice(1)} priority`
}

function priorityVariant(priority: ProspectingPriority) {
  if (priority === "high") return "default"
  if (priority === "medium") return "secondary"
  return "outline"
}

function BulletList({ items, variant = "neutral" }: { items: string[]; variant?: "neutral" | "danger" | "success" }) {
  if (!items.length) {
    return <p className="text-xs text-muted-foreground italic">No items identified yet.</p>
  }
  return (
    <ul className="space-y-2 text-xs">
      {items.map((item, idx) => (
        <li
          key={idx}
          className={`flex items-start gap-2.5 rounded-lg border p-2.5 transition-colors ${
            variant === "danger"
              ? "border-amber-500/25 bg-amber-500/[0.04] text-foreground"
              : variant === "success"
              ? "border-emerald-500/25 bg-emerald-500/[0.04] text-foreground"
              : "border-border/70 bg-muted/30 text-foreground/90"
          }`}
        >
          <span
            className={`mt-1 size-1.5 shrink-0 rounded-full ${
              variant === "danger"
                ? "bg-amber-500"
                : variant === "success"
                ? "bg-emerald-500"
                : "bg-primary"
            }`}
          />
          <span className="leading-relaxed font-normal">{item}</span>
        </li>
      ))}
    </ul>
  )
}

function DraftPanel({
  title,
  icon: Icon,
  value,
  copyLabel,
  onCopy,
}: {
  title: string
  icon: typeof Mail
  value: string
  copyLabel: string
  onCopy: () => void
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    onCopy()
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="group relative rounded-xl border border-border/80 bg-gradient-to-b from-card to-background p-4 shadow-sm transition-all hover:border-primary/40">
      <div className="flex items-center justify-between pb-3 border-b border-border/60">
        <div className="flex items-center gap-2">
          <div className="rounded-md bg-primary/10 p-1.5 text-primary">
            <Icon className="size-3.5" />
          </div>
          <span className="text-xs font-semibold text-foreground tracking-tight">
            {title}
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 px-2.5 text-xs gap-1.5 hover:bg-primary/10 hover:text-primary transition-colors"
          aria-label={copyLabel}
          onClick={handleCopy}
        >
          {copied ? (
            <>
              <CheckCircle2 className="size-3 text-emerald-500" />
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="size-3" />
              <span className="text-[11px]">Copy</span>
            </>
          )}
        </Button>
      </div>
      <pre className="mt-3 min-h-24 whitespace-pre-wrap font-sans text-xs leading-relaxed text-foreground/90 font-normal">
        {value}
      </pre>
    </div>
  )
}

export default function ProspectingPage() {
  const [contacts, setContacts] = useState<ProspectingReadyContact[]>([])
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([])
  const [selectedContactId, setSelectedContactId] = useState("")
  const [campaigns, setCampaigns] = useState<ProspectingCampaign[]>([])
  const [sequences, setSequences] = useState<ProspectingSequence[]>([])
  const [selectedCampaignId, setSelectedCampaignId] = useState("")
  const [selectedSequenceId, setSelectedSequenceId] = useState("")
  const [search, setSearch] = useState("")
  const [filterPriority, setFilterPriority] = useState<string>("all")
  const [companyUrl, setCompanyUrl] = useState("")
  const [result, setResult] = useState<ProspectingResearchResult | null>(null)
  const [history, setHistory] = useState<ProspectingResearchResult[]>([])
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [researching, setResearching] = useState(false)
  const [bulkResearching, setBulkResearching] = useState(false)
  const [enrolling, setEnrolling] = useState(false)
  const [feedback, setFeedback] = useState("")

  const selectedContact = useMemo(
    () => contacts.find((contact) => contact.id === selectedContactId) || null,
    [contacts, selectedContactId],
  )

  const selectedCampaignSequences = useMemo(
    () =>
      sequences.filter(
        (sequence) => sequence.campaign_id === selectedCampaignId,
      ),
    [sequences, selectedCampaignId],
  )

  const filteredContacts = useMemo(() => {
    return contacts.filter((c) => {
      if (filterPriority === "high" && c.priority !== "high") return false
      if (filterPriority === "medium" && c.priority !== "medium") return false
      if (filterPriority === "handoff" && !c.handoff_source) return false
      return true
    })
  }, [contacts, filterPriority])

  const metrics = useMemo(() => {
    const total = contacts.length
    const highPriority = contacts.filter((c) => c.priority === "high").length
    const handoffs = contacts.filter((c) => Boolean(c.handoff_source)).length
    const voiceReady = contacts.filter((c) => Boolean(c.phone)).length
    return { total, highPriority, handoffs, voiceReady }
  }, [contacts])

  const loadContacts = useCallback(
    async (nextSearch = search) => {
      setLoadingContacts(true)
      setFeedback("")
      try {
        const response = await listReadyContacts(nextSearch)
        setContacts(response.data)
        setSelectedContactIds((current) =>
          current.filter((id) =>
            response.data.some((contact) => contact.id === id),
          ),
        )
        setSelectedContactId((current) => {
          if (
            current &&
            response.data.some((contact) => contact.id === current)
          ) {
            return current
          }
          return response.data[0]?.id || ""
        })
      } catch (error) {
        setFeedback(
          error instanceof Error ? error.message : "Could not load contacts",
        )
      } finally {
        setLoadingContacts(false)
      }
    },
    [search],
  )

  const loadOutreachTargets = useCallback(async () => {
    try {
      const [campaignResponse, sequenceResponse] = await Promise.all([
        listProspectingCampaigns(),
        listProspectingSequences(),
      ])
      setCampaigns(campaignResponse.data)
      setSequences(sequenceResponse.data)
      setSelectedCampaignId(
        (current) => current || campaignResponse.data[0]?.id || "",
      )
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not load outreach targets",
      )
    }
  }, [])

  useEffect(() => {
    void loadContacts("")
    void loadOutreachTargets()
  }, [loadContacts, loadOutreachTargets])

  useEffect(() => {
    if (!selectedCampaignId) {
      setSelectedSequenceId("")
      return
    }
    setSelectedSequenceId((current) => {
      if (
        current &&
        selectedCampaignSequences.some((sequence) => sequence.id === current)
      ) {
        return current
      }
      return selectedCampaignSequences[0]?.id || ""
    })
  }, [selectedCampaignId, selectedCampaignSequences])

  const loadHistory = useCallback(async (contactId: string) => {
    setLoadingHistory(true)
    try {
      const response = await listProspectingResearch(contactId)
      setHistory(response.data)
      setResult(response.data[0] || null)
    } catch (error) {
      setHistory([])
      setResult(null)
      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not load research history",
      )
    } finally {
      setLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    if (!selectedContactId) {
      setHistory([])
      setResult(null)
      return
    }
    setResult(null)
    void loadHistory(selectedContactId)
  }, [selectedContactId, loadHistory])

  async function runResearch() {
    if (!selectedContactId) return
    setResearching(true)
    setFeedback("")
    try {
      const payload = await runProspectingResearch({
        contact_id: selectedContactId,
        company_url: companyUrl.trim() || null,
      })
      setResult(payload)
      setHistory((current) => [
        payload,
        ...current.filter((item) => item.id !== payload.id),
      ])
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not run prospecting research",
      )
    } finally {
      setResearching(false)
    }
  }

  function toggleSelectedContact(contactId: string) {
    setSelectedContactIds((current) =>
      current.includes(contactId)
        ? current.filter((id) => id !== contactId)
        : [...current, contactId],
    )
  }

  function selectAllContacts() {
    setSelectedContactIds(contacts.map((contact) => contact.id))
  }

  async function runSelectedResearch() {
    if (selectedContactIds.length === 0) return
    setBulkResearching(true)
    setFeedback("")
    try {
      const payload = await runBulkProspectingResearch({
        contact_ids: selectedContactIds,
        company_url: companyUrl.trim() || null,
      })
      const nextResult =
        payload.data.find(
          (snapshot) => snapshot.contact_id === selectedContactId,
        ) ||
        payload.data[0] ||
        null
      setResult(nextResult)
      if (nextResult?.contact_id === selectedContactId) {
        setHistory((current) => [
          nextResult,
          ...current.filter((item) => item.id !== nextResult.id),
        ])
      }
      setFeedback(`Researched ${payload.count} selected prospects.`)
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not run selected prospecting research",
      )
    } finally {
      setBulkResearching(false)
    }
  }

  async function addSelectedToOutreach() {
    if (selectedContactIds.length === 0 || !selectedCampaignId) return
    setEnrolling(true)
    setFeedback("")
    try {
      const payload = await enrollProspects({
        contact_ids: selectedContactIds,
        campaign_id: selectedCampaignId,
        sequence_id: selectedSequenceId || null,
      })
      setFeedback(payload.message)
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not add selected prospects to outreach",
      )
    } finally {
      setEnrolling(false)
    }
  }

  async function copyDraft(label: string, value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setFeedback(`${label} copied.`)
    } catch {
      setFeedback(`Could not copy ${label.toLowerCase()}.`)
    }
  }

  return (
    <WorkspacePage
      eyebrow="Accounts"
      icon={Search}
      title="Lead Preparation"
      description="Turn warm CRM signals and Messaging Hub handoffs into outreach briefs and verified voice openers."
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => void loadContacts(search)}
          disabled={loadingContacts}
        >
          {loadingContacts ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          Refresh queue
        </Button>
      }
      metrics={[
        {
          label: "Leads needing follow-up",
          value: metrics.total,
          hint: "Queued in CRM context",
          icon: Users,
        },
        {
          label: "High priority intent",
          value: metrics.highPriority,
          hint: "Ready for immediate brief",
          icon: Flame,
          tone: "success",
        },
        {
          label: "Messaging Hub handoffs",
          value: metrics.handoffs,
          hint: "Live chat and bot origins",
          icon: MessageSquare,
          tone: "info",
        },
        {
          label: "Voice ready contacts",
          value: metrics.voiceReady,
          hint: "Phone number verified",
          icon: Phone,
        },
      ]}
    >

      {feedback && (
        <Alert className="border-primary/30 bg-primary/5 text-primary text-xs flex items-center justify-between">
          <span>{feedback}</span>
          <button type="button" onClick={() => setFeedback("")} className="text-xs text-muted-foreground hover:text-foreground">
            Dismiss
          </button>
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[410px_minmax(0,1fr)]">
        <Card className="flex min-h-[640px] flex-col border border-border/80 shadow-xs xl:h-[calc(100vh-16rem)]">
          <CardHeader className="space-y-3 border-b border-border/60 bg-muted/15 p-4 pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-semibold tracking-tight flex items-center gap-2">
                  <UserCheck className="size-4 text-primary" />
                  Leads needing follow-up
                </CardTitle>
                <CardDescription className="text-[11px] text-muted-foreground mt-0.5">
                  Prioritized by buyer intent and activity
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-[11px] font-mono">
                {contacts.length} pool
              </Badge>
            </div>

            {/* Quick Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
              <Input
                id="prospecting-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void loadContacts(search)
                }}
                placeholder="Search by name, company, or email..."
                className="h-8.5 pl-8 text-xs bg-background"
              />
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap items-center justify-between gap-1 pt-0.5">
              <div className="flex gap-1">
                {[
                  { id: "all", label: "All" },
                  { id: "high", label: "High Priority" },
                  { id: "handoff", label: "Messaging Hub" },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFilterPriority(f.id)}
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium transition ${
                      filterPriority === f.id
                        ? "bg-primary text-primary-foreground font-semibold"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Multi-select Controls */}
              <div className="flex items-center gap-1.5 text-[11px]">
                <button
                  type="button"
                  onClick={selectAllContacts}
                  className="text-primary hover:underline font-medium text-[11px]"
                >
                  Select all
                </button>
                <span className="text-muted-foreground">•</span>
                <button
                  type="button"
                  onClick={() => setSelectedContactIds([])}
                  className="text-muted-foreground hover:underline text-[11px]"
                >
                  Clear
                </button>
                {selectedContactIds.length > 0 && (
                  <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-0.5 font-bold">
                    {selectedContactIds.length}
                  </Badge>
                )}
              </div>
            </div>

            {/* Accessible Contact select for test automation */}
            <div className="sr-only">
              <Label htmlFor="prospecting-contact">Contact</Label>
              <select
                id="prospecting-contact"
                value={selectedContactId}
                onChange={(event) => setSelectedContactId(event.target.value)}
              >
                {contacts.length === 0 ? (
                  <option value="">No contacts found</option>
                ) : (
                  contacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {contactLabel(contact)}
                    </option>
                  ))
                )}
              </select>
            </div>
          </CardHeader>

          {/* List of Contacts */}
          <CardContent className="p-3 flex-1 overflow-y-auto space-y-2">
            {filteredContacts.length === 0 && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/80 p-8 text-center text-xs text-muted-foreground">
                <Compass className="size-6 text-muted-foreground/40 mb-2" />
                <p className="font-medium text-foreground">No leads found in this view</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Try clearing filters or search criteria.</p>
              </div>
            )}

            {filteredContacts.map((contact) => {
              const isSelectedRow = contact.id === selectedContactId
              const isChecked = selectedContactIds.includes(contact.id)

              return (
                <div
                  key={contact.id}
                  onClick={() => setSelectedContactId(contact.id)}
                  className={`group relative flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-left transition-all ${
                    isSelectedRow
                      ? "border-primary bg-primary/[0.04] shadow-xs ring-1 ring-primary/20"
                      : "border-border/70 bg-card hover:border-primary/40 hover:bg-muted/30"
                  }`}
                >
                  {/* Select Checkbox */}
                  <div
                    className="pt-0.5"
                    onClick={(e) => {
                      e.stopPropagation()
                    }}
                  >
                    <input
                      type="checkbox"
                      className="size-4 rounded border-border accent-primary cursor-pointer"
                      aria-label={`Select ${contactLabel(contact)}`}
                      checked={isChecked}
                      onChange={() => toggleSelectedContact(contact.id)}
                    />
                  </div>

                  {/* Contact Summary Info */}
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-start justify-between gap-1.5">
                      <span className="truncate text-xs font-semibold text-foreground group-hover:text-primary transition-colors">
                        {contactLabel(contact)}
                      </span>
                      <Badge
                        variant={priorityVariant(contact.priority)}
                        className="text-[10px] px-1.5 py-0 shrink-0 font-medium tracking-tight"
                      >
                        {priorityLabel(contact.priority)}
                      </Badge>
                    </div>

                    <div className="truncate text-[11px] text-muted-foreground">
                      {contact.email}
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-[10px] font-bold text-foreground">
                        <Flame className="size-2.5 text-amber-500" />
                        Score {contact.lead_score}
                      </span>
                      {contact.handoff_source && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-400">
                          <Bot className="size-2.5" />
                          Messaging Hub
                        </span>
                      )}
                      {contact.phone && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground font-medium">
                          <Phone className="size-2.5 text-emerald-500" />
                          Voice ready
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>

        {/* Right Card: Intelligence Dossier & Action Console */}
        <div className="space-y-6">
          {/* Active Contact Command Header Card */}
          <Card className="border border-border/80 shadow-xs overflow-hidden">
            <div className="bg-gradient-to-r from-primary/10 via-muted/40 to-background p-5 border-b border-border/60">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-bold tracking-tight text-foreground">
                      {selectedContact ? contactLabel(selectedContact) : "Select a Prospect to Prepare"}
                    </h2>
                    {selectedContact && (
                      <Badge variant={priorityVariant(selectedContact.priority)} className="text-xs">
                        {priorityLabel(selectedContact.priority)}
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Mail className="size-3.5" />
                      {selectedContact?.email || "No email available"}
                    </span>
                    {selectedContact?.company && (
                      <span className="flex items-center gap-1 font-medium text-foreground">
                        <Building2 className="size-3.5 text-primary" />
                        {selectedContact.company}
                      </span>
                    )}
                    {selectedContact?.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="size-3.5" />
                        {selectedContact.phone}
                      </span>
                    )}
                  </div>
                </div>

                {/* Primary Action Buttons */}
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    className="h-9 gap-1.5 text-xs font-semibold shadow-xs"
                    onClick={runResearch}
                    disabled={!selectedContactId || researching}
                  >
                    {researching ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="size-3.5 text-amber-300" />
                    )}
                    Build lead brief
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 gap-1.5 text-xs hover:border-primary/50"
                    onClick={() => void runSelectedResearch()}
                    disabled={selectedContactIds.length === 0 || bulkResearching}
                  >
                    {bulkResearching ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Users className="size-3.5 text-primary" />
                    )}
                    Build briefs for selected
                    {selectedContactIds.length > 0 && (
                      <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0 h-4">
                        {selectedContactIds.length}
                      </Badge>
                    )}
                  </Button>
                </div>
              </div>

              {/* Company Website URL & Scoring Signals */}
              <div className="mt-4 pt-3 border-t border-border/50 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <Label htmlFor="prospecting-company-url" className="text-xs shrink-0 text-muted-foreground font-medium">
                    Company website:
                  </Label>
                  <div className="relative">
                    <Globe className="absolute left-2.5 top-2 size-3 text-muted-foreground" />
                    <Input
                      id="prospecting-company-url"
                      value={companyUrl}
                      onChange={(event) => setCompanyUrl(event.target.value)}
                      placeholder="https://company.example"
                      inputMode="url"
                      className="h-7.5 pl-7.5 text-xs bg-background max-w-xs"
                    />
                  </div>
                </div>

                {selectedContact?.priority_reasons && selectedContact.priority_reasons.length > 0 && (
                  <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                    <span className="font-semibold text-foreground">Signals:</span>
                    <span>{selectedContact.priority_reasons.join(" • ")}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Campaign & Sequence Enrollment Toolbar */}
            <div className="p-4 bg-muted/20 border-b border-border/60">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-2">
                  <div className="rounded-md bg-primary/10 p-1 text-primary">
                    <Send className="size-3.5" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-foreground">
                      Outreach handoff
                    </span>
                    <span className="ml-1.5 text-[11px] text-muted-foreground">
                      (enrolling {selectedContactIds.length || 1} selected lead{selectedContactIds.length === 1 ? "" : "s"})
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="prospecting-campaign" className="text-xs text-muted-foreground">
                      Campaign
                    </Label>
                    <select
                      id="prospecting-campaign"
                      className="h-8 rounded-md border border-border/80 bg-background px-2.5 text-xs"
                      value={selectedCampaignId}
                      onChange={(event) => setSelectedCampaignId(event.target.value)}
                      disabled={campaigns.length === 0}
                    >
                      {campaigns.length === 0 ? (
                        <option value="">No campaigns</option>
                      ) : (
                        campaigns.map((campaign) => (
                          <option key={campaign.id} value={campaign.id}>
                            {campaign.name}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="prospecting-sequence" className="text-xs text-muted-foreground">
                      Sequence
                    </Label>
                    <select
                      id="prospecting-sequence"
                      className="h-8 rounded-md border border-border/80 bg-background px-2.5 text-xs"
                      value={selectedSequenceId}
                      onChange={(event) => setSelectedSequenceId(event.target.value)}
                      disabled={!selectedCampaignId || selectedCampaignSequences.length === 0}
                    >
                      {selectedCampaignSequences.length === 0 ? (
                        <option value="">No sequence</option>
                      ) : (
                        selectedCampaignSequences.map((sequence) => (
                          <option key={sequence.id} value={sequence.id}>
                            {sequence.name}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <Button
                    size="sm"
                    className="h-8 gap-1.5 text-xs"
                    onClick={() => void addSelectedToOutreach()}
                    disabled={selectedContactIds.length === 0 || !selectedCampaignId || enrolling}
                  >
                    {enrolling ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Send className="size-3.5" />
                    )}
                    Add selected to outreach
                  </Button>
                </div>
              </div>
            </div>

            {/* AI Lead Brief Content Area */}
            <CardContent className="p-5">
              {result ? (
                <div className="space-y-6">
                  {/* Account Summary Banner */}
                  <div className="rounded-xl border border-primary/25 bg-gradient-to-r from-primary/[0.08] to-background p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                        <Sparkles className="size-3.5" />
                        Account summary
                      </h3>
                      <span className="text-[11px] text-muted-foreground">
                        Synthesized {new Date(result.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-relaxed text-foreground">
                      {result.account_summary}
                    </p>
                    <div className="flex items-start gap-2 pt-1 text-xs text-muted-foreground">
                      <CheckCircle2 className="size-3.5 text-emerald-500 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-foreground">Recommended Next Action:</span>{" "}
                        <span className="text-foreground/90">{result.suggested_next_action}</span>
                      </div>
                    </div>
                  </div>

                  {/* Pain Points vs Objections (Side-by-Side Cards) */}
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-border/80 bg-card p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                          <Zap className="size-3.5 text-amber-500" />
                          Pain points
                        </h4>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {result.pain_points.length} identified
                        </Badge>
                      </div>
                      <BulletList items={result.pain_points} variant="danger" />
                    </div>

                    <div className="rounded-xl border border-border/80 bg-card p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                          <Layers className="size-3.5 text-blue-500" />
                          Likely objections
                        </h4>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {result.objections.length} anticipated
                        </Badge>
                      </div>
                      <BulletList items={result.objections} variant="neutral" />
                    </div>
                  </div>

                  {/* Personalization Angles */}
                  <div className="rounded-xl border border-border/80 bg-card p-4 space-y-2.5">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <Sparkles className="size-3.5 text-primary" />
                      Personalization
                    </h4>
                    <BulletList items={result.personalization_bullets} variant="success" />
                  </div>

                  {/* Grounding Sources */}
                  {result.sources && result.sources.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">Grounding sources:</span>
                      {result.sources.map((source, sIdx) => (
                        <Badge key={sIdx} variant="secondary" className="text-[10px]">
                          {source.label}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <Separator />

                  {/* Outreach Drafts (Side-by-Side Console) */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <Send className="size-3.5 text-primary" />
                        AI generated outreach scripts
                      </h4>
                      <span className="text-[11px] text-muted-foreground">
                        Ready for 1-click copy or sequence push
                      </span>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-2">
                      <DraftPanel
                        title="Email draft"
                        icon={Mail}
                        value={result.email_draft}
                        copyLabel="Copy email draft"
                        onCopy={() => void copyDraft("Email draft", result.email_draft)}
                      />
                      <DraftPanel
                        title="Voice opener"
                        icon={Phone}
                        value={result.voice_opener}
                        copyLabel="Copy voice opener"
                        onCopy={() => void copyDraft("Voice opener", result.voice_opener)}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                /* Sleek Lively Initial State with Graphic Illustration */
                <div className="relative overflow-hidden rounded-2xl border border-dashed border-border/80 bg-muted/10 p-8 text-center sm:p-12">
                  <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-xs">
                    <Sparkles className="size-7" />
                  </div>
                  <h3 className="mt-4 text-base font-bold tracking-tight text-foreground sm:text-lg">
                    Build a brief for the selected lead.
                  </h3>
                  <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-muted-foreground">
                    Select a contact from the left queue and click <strong className="text-foreground">"Build lead brief"</strong> to synthesize account background, objection handling, tailored cold email drafts, and voice dialer scripts.
                  </p>

                  <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                    <Button
                      size="sm"
                      onClick={runResearch}
                      disabled={!selectedContactId || researching}
                      className="gap-1.5 text-xs font-semibold"
                    >
                      {researching ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                      Synthesize Brief Now
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Research History Timeline */}
          <Card className="border border-border/80 shadow-xs">
            <CardHeader className="py-3 px-4.5 flex flex-row items-center justify-between border-b border-border/60 bg-muted/20">
              <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                <Clock3 className="size-3.5 text-primary" />
                <span>Research history ({history.length})</span>
              </div>
              {loadingHistory && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
            </CardHeader>
            <CardContent className="p-3">
              {history.length ? (
                <div className="max-h-40 space-y-2 overflow-y-auto">
                  {history.map((snapshot) => (
                    <button
                      key={snapshot.id}
                      type="button"
                      className={`w-full rounded-xl border p-2.5 text-left text-xs transition-all ${
                        result?.id === snapshot.id
                          ? "border-primary bg-primary/[0.04] shadow-xs"
                          : "border-border/70 bg-background hover:bg-muted/40"
                      }`}
                      onClick={() => setResult(snapshot)}
                    >
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                        <span className="font-semibold text-foreground">Snapshot</span>
                        <span>{new Date(snapshot.created_at).toLocaleString()}</span>
                      </div>
                      <div className="mt-1 text-xs text-foreground/90 font-medium truncate">
                        {snapshot.account_summary}
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-muted-foreground">
                  No previous research snapshots yet.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </WorkspacePage>
  )
}