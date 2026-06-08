import { useEffect, useMemo, useState } from "react"
import { Clock3, Copy, Loader2, RefreshCw, SearchCheck, Sparkles } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  listProspectingResearch,
  listReadyContacts,
  runProspectingResearch,
  type ProspectingPriority,
  type ProspectingReadyContact,
  type ProspectingResearchResult,
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

function BulletList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">No items yet.</p>
  }
  return (
    <ul className="space-y-2 text-sm">
      {items.map((item) => (
        <li key={item} className="rounded-md border bg-muted/30 px-3 py-2">
          {item}
        </li>
      ))}
    </ul>
  )
}

function DraftPanel({
  title,
  value,
  copyLabel,
  onCopy,
}: {
  title: string
  value: string
  copyLabel: string
  onCopy: () => void
}) {
  return (
    <div className="rounded-md border bg-background">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="text-sm font-medium">{title}</div>
        <Button type="button" variant="ghost" size="sm" aria-label={copyLabel} onClick={onCopy}>
          <Copy className="size-4" />
        </Button>
      </div>
      <pre className="min-h-28 whitespace-pre-wrap px-3 py-3 text-sm leading-6 text-foreground">
        {value}
      </pre>
    </div>
  )
}

export default function ProspectingPage() {
  const [contacts, setContacts] = useState<ProspectingReadyContact[]>([])
  const [selectedContactId, setSelectedContactId] = useState("")
  const [search, setSearch] = useState("")
  const [companyUrl, setCompanyUrl] = useState("")
  const [result, setResult] = useState<ProspectingResearchResult | null>(null)
  const [history, setHistory] = useState<ProspectingResearchResult[]>([])
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [researching, setResearching] = useState(false)
  const [feedback, setFeedback] = useState("")

  const selectedContact = useMemo(
    () => contacts.find((contact) => contact.id === selectedContactId) || null,
    [contacts, selectedContactId],
  )

  async function loadContacts(nextSearch = search) {
    setLoadingContacts(true)
    setFeedback("")
    try {
      const response = await listReadyContacts(nextSearch)
      setContacts(response.data)
      setSelectedContactId((current) => {
        if (current && response.data.some((contact) => contact.id === current)) {
          return current
        }
        return response.data[0]?.id || ""
      })
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Could not load contacts")
    } finally {
      setLoadingContacts(false)
    }
  }

  useEffect(() => {
    void loadContacts("")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadHistory(contactId: string) {
    setLoadingHistory(true)
    try {
      const response = await listProspectingResearch(contactId)
      setHistory(response.data)
      setResult(response.data[0] || null)
    } catch (error) {
      setHistory([])
      setResult(null)
      setFeedback(error instanceof Error ? error.message : "Could not load research history")
    } finally {
      setLoadingHistory(false)
    }
  }

  useEffect(() => {
    if (!selectedContactId) {
      setHistory([])
      setResult(null)
      return
    }
    setResult(null)
    void loadHistory(selectedContactId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedContactId])

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
      setHistory((current) => [payload, ...current.filter((item) => item.id !== payload.id)])
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Could not run prospecting research")
    } finally {
      setResearching(false)
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
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <SearchCheck className="size-4" />
            Account research
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Prospecting</h1>
          <p className="text-sm text-muted-foreground">
            Enrich an existing contact with CRM context and draft personalized outreach.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadContacts(search)} disabled={loadingContacts}>
          {loadingContacts ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Refresh
        </Button>
      </div>

      {feedback && <Alert>{feedback}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Ready for prospecting</CardTitle>
            <CardDescription>Ranked by chatbot handoffs, buyer intent, contactability, and account context.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="prospecting-search">Search contacts</Label>
              <div className="flex gap-2">
                <Input
                  id="prospecting-search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Company, name, or email"
                />
                <Button type="button" variant="outline" onClick={() => void loadContacts(search)} disabled={loadingContacts}>
                  {loadingContacts ? <Loader2 className="size-4 animate-spin" /> : <SearchCheck className="size-4" />}
                  <span className="sr-only">Search</span>
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="font-medium">Handoff queue</span>
                <Badge variant="outline">{contacts.length} contacts</Badge>
              </div>
              {contacts.length ? (
                <div className="space-y-2">
                  {contacts.map((contact) => (
                    <button
                      key={contact.id}
                      type="button"
                      className={`w-full rounded-md border px-3 py-2 text-left transition hover:bg-muted/60 ${
                        contact.id === selectedContactId ? "border-primary bg-muted/40" : "bg-background"
                      }`}
                      onClick={() => setSelectedContactId(contact.id)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">{contactLabel(contact)}</div>
                          <div className="truncate text-xs text-muted-foreground">{contact.email}</div>
                        </div>
                        <Badge variant={priorityVariant(contact.priority)}>
                          {priorityLabel(contact.priority)}
                        </Badge>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge variant="outline">Score {contact.lead_score}</Badge>
                        {contact.handoff_source && <Badge variant="secondary">Messaging Hub</Badge>}
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed px-3 py-5 text-center text-sm text-muted-foreground">
                  No contacts found.
                </div>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="prospecting-contact">Contact</Label>
              <select
                id="prospecting-contact"
                className="h-10 rounded-md border bg-background px-3 text-sm"
                value={selectedContactId}
                onChange={(event) => setSelectedContactId(event.target.value)}
                disabled={loadingContacts || contacts.length === 0}
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

            <div className="grid gap-2">
              <Label htmlFor="prospecting-company-url">Company website</Label>
              <Input
                id="prospecting-company-url"
                value={companyUrl}
                onChange={(event) => setCompanyUrl(event.target.value)}
                placeholder="https://company.example"
                inputMode="url"
              />
            </div>

            {selectedContact && (
              <div className="rounded-md border bg-muted/30 p-3 text-sm">
                <div className="font-medium">{contactLabel(selectedContact)}</div>
                <div className="mt-1 text-muted-foreground">{selectedContact.email}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant={priorityVariant(selectedContact.priority)}>
                    {priorityLabel(selectedContact.priority)}
                  </Badge>
                  <Badge variant="outline">Score {selectedContact.lead_score}</Badge>
                  {selectedContact.handoff_source && <Badge variant="secondary">Messaging Hub</Badge>}
                  {selectedContact.phone && <Badge variant="secondary">Voice ready</Badge>}
                  {selectedContact.company && <Badge variant="outline">{selectedContact.company}</Badge>}
                </div>
                {selectedContact.priority_reasons.length > 0 && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    {selectedContact.priority_reasons.join(" | ")}
                  </div>
                )}
              </div>
            )}

            <Button className="w-full" onClick={runResearch} disabled={!selectedContactId || researching}>
              {researching ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Sparkles className="mr-2 size-4" />}
              Run research
            </Button>

            <div className="rounded-md border bg-background">
              <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Clock3 className="size-4" />
                  Research history
                </div>
                {loadingHistory && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
              </div>
              <div className="max-h-72 space-y-2 overflow-auto p-3">
                {history.length ? (
                  history.map((snapshot) => (
                    <button
                      key={snapshot.id}
                      type="button"
                      className={`w-full rounded-md border px-3 py-2 text-left text-sm transition hover:bg-muted/60 ${
                        result?.id === snapshot.id ? "border-primary bg-muted/40" : "bg-background"
                      }`}
                      onClick={() => setResult(snapshot)}
                    >
                      <div className="text-xs text-muted-foreground">
                        {new Date(snapshot.created_at).toLocaleString()}
                      </div>
                      <div className="mt-1 leading-5">{snapshot.account_summary}</div>
                    </button>
                  ))
                ) : (
                  <div className="rounded-md border border-dashed px-3 py-5 text-center text-sm text-muted-foreground">
                    No research snapshots yet.
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Research brief</CardTitle>
              <CardDescription>
                {result ? `Snapshot created ${new Date(result.created_at).toLocaleString()}` : "Run research to generate a brief."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {result ? (
                <>
                  <div>
                    <h2 className="text-base font-semibold">Account summary</h2>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{result.account_summary}</p>
                  </div>
                  <Separator />
                  <div className="grid gap-5 lg:grid-cols-2">
                    <div>
                      <h2 className="mb-3 text-base font-semibold">Pain points</h2>
                      <BulletList items={result.pain_points} />
                    </div>
                    <div>
                      <h2 className="mb-3 text-base font-semibold">Likely objections</h2>
                      <BulletList items={result.objections} />
                    </div>
                  </div>
                  <div>
                    <h2 className="mb-3 text-base font-semibold">Personalization</h2>
                    <BulletList items={result.personalization_bullets} />
                  </div>
                  <div className="rounded-md border bg-muted/30 px-3 py-3 text-sm">
                    <span className="font-medium">Next action: </span>
                    {result.suggested_next_action}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {result.sources.map((source) => (
                      <Badge key={`${source.label}-${source.summary}`} variant="secondary">
                        {source.label}
                      </Badge>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex min-h-72 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
                  Select a contact and run research.
                </div>
              )}
            </CardContent>
          </Card>

          {result && (
            <div className="grid gap-6 lg:grid-cols-2">
              <DraftPanel
                title="Email draft"
                value={result.email_draft}
                copyLabel="Copy email draft"
                onCopy={() => void copyDraft("Email draft", result.email_draft)}
              />
              <DraftPanel
                title="Voice opener"
                value={result.voice_opener}
                copyLabel="Copy voice opener"
                onCopy={() => void copyDraft("Voice opener", result.voice_opener)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
