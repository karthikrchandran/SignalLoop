import { Link } from "@tanstack/react-router"
import { useEffect, useMemo, useState } from "react"
import { Download, Loader2, RefreshCw, Search, Upload, Users } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  criterionLabel,
  leadGroups,
  matchesLeadGroup,
} from "@/features/contacts/leadGroups"
import { signalloopRequest } from "@/lib/signalloop-api"

type Contact = {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  company: string | null
  phone: string | null
  timezone: string
  created_at: string
  industry?: string | null
  title?: string | null
  product_interest?: string | null
  source?: string | null
}

type ContactsResponse = { data: Contact[]; count: number }

type ImportRowError = {
  row_number: number
  column: string
  message: string
}

type PreviewRow = { row_number: number; data: Record<string, unknown> }

type ContactImportResponse = {
  total_rows: number
  valid_rows: number
  invalid_rows: number
  created_count: number
  updated_count: number
  committed: boolean
  requires_mapping: boolean
  headers: string[]
  mapping: Record<string, string>
  preview_rows: PreviewRow[]
  errors: ImportRowError[]
}

type ContactManagementPageProps = {
  leadGroupId?: string
}

const canonicalFields = ["email", "firstName", "lastName", "company", "phone", "timezone"]

const fieldLabels: Record<string, string> = {
  email: "Email",
  firstName: "First name",
  lastName: "Last name",
  company: "Company",
  phone: "Phone",
  timezone: "Timezone",
}

const templateCsv = [
  "email,firstName,lastName,company,phone,timezone",
  "ada@example.com,Ada,Lovelace,Analytical,+15551234567,America/New_York",
].join("\n")

function contactName(contact: Contact) {
  return [contact.first_name, contact.last_name].filter(Boolean).join(" ") || "-"
}

export default function ContactManagementPage({ leadGroupId }: ContactManagementPageProps) {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [count, setCount] = useState(0)
  const [search, setSearch] = useState("")
  const [industryFilter, setIndustryFilter] = useState("all")
  const [titleFilter, setTitleFilter] = useState("all")
  const [interestFilter, setInterestFilter] = useState("all")
  const [sourceFilter, setSourceFilter] = useState("all")
  const [page, setPage] = useState(1)
  const [file, setFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<ContactImportResponse | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)
  const [loadingContacts, setLoadingContacts] = useState(false)
  const pageSize = 10

  const mappedFields = useMemo(
    () => canonicalFields.filter((field) => mapping[field]).length,
    [mapping],
  )

  const uniqueValues = (field: keyof Contact) =>
    Array.from(new Set(contacts.map((contact) => contact[field]).filter(Boolean).map(String))).sort()

  const filteredContacts = contacts.filter((contact) => {
    if (industryFilter !== "all" && contact.industry !== industryFilter) return false
    if (titleFilter !== "all" && contact.title !== titleFilter) return false
    if (interestFilter !== "all" && contact.product_interest !== interestFilter) return false
    if (sourceFilter !== "all" && contact.source !== sourceFilter) return false
    return true
  })

  const pageCount = Math.max(1, Math.ceil(filteredContacts.length / pageSize))
  const pagedContacts = filteredContacts.slice((page - 1) * pageSize, page * pageSize)
  const selectedLeadGroup = leadGroups.find((group) => group.id === leadGroupId)
  const selectedLeadGroupContacts = selectedLeadGroup
    ? contacts.filter((contact) => matchesLeadGroup(contact, selectedLeadGroup))
    : []

  async function loadContacts(nextSearch = search) {
    setLoadingContacts(true)
    try {
      const params = new URLSearchParams()
      if (nextSearch.trim()) params.set("search", nextSearch.trim())
      const response = await signalloopRequest<ContactsResponse>(`/api/v1/contacts/?${params.toString()}`)
      setContacts(response.data)
      setCount(response.count)
      setPage(1)
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

  async function run(action: () => Promise<void>) {
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

  async function analyzeCsv() {
    if (!file) return
    await run(async () => {
      const formData = new FormData()
      formData.append("file", file)
      const result = await signalloopRequest<ContactImportResponse>("/api/v1/contacts/import", {
        method: "POST",
        formData,
      })
      setImportResult(result)
      setMapping(result.mapping)
      setFeedback(`Analyzed ${result.total_rows} rows: ${result.valid_rows} valid, ${result.invalid_rows} invalid.`)
    })
  }

  async function importContacts() {
    if (!file) return
    await run(async () => {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("mapping_json", JSON.stringify(mapping))
      formData.append("commit", "true")
      const result = await signalloopRequest<ContactImportResponse>("/api/v1/contacts/import", {
        method: "POST",
        formData,
      })
      setImportResult(result)
      if (result.committed) {
        setFeedback(`Imported ${result.created_count} new and updated ${result.updated_count} existing contacts.`)
        await loadContacts("")
      } else {
        setFeedback(`Import not saved: ${result.invalid_rows} rows need attention.`)
      }
    })
  }

  function downloadTemplate() {
    const blob = new Blob([templateCsv], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "signalloop-contacts-template.csv"
    link.click()
    URL.revokeObjectURL(url)
  }

  function resetFilters() {
    setIndustryFilter("all")
    setTitleFilter("all")
    setInterestFilter("all")
    setSourceFilter("all")
    setPage(1)
  }

  if (selectedLeadGroup) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <Button asChild variant="outline">
            <Link to="/contacts">Back to Contacts</Link>
          </Button>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">{selectedLeadGroup.name}</h1>
          <p className="text-sm text-muted-foreground">{selectedLeadGroup.description}</p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Group criteria</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {selectedLeadGroup.criteria.map((criterion) => (
              <Badge
                key={`${criterion.field}-${criterion.operator}-${criterion.value || "exists"}`}
                variant="outline"
              >
                {criterionLabel(criterion)}
              </Badge>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Matching leads</CardTitle>
            <CardDescription>{selectedLeadGroupContacts.length} matching lead(s)</CardDescription>
          </CardHeader>
          <CardContent>
            <ContactTable contacts={selectedLeadGroupContacts} />
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Contacts</h1>
          <p className="text-sm text-muted-foreground">{count} lead{count === 1 ? "" : "s"} in the active workspace</p>
        </div>
        <Button variant="outline" onClick={downloadTemplate}>
          <Download className="mr-2 size-4" />
          CSV template
        </Button>
      </div>

      {feedback && (
        <Alert>
          <p className="text-sm">{feedback}</p>
        </Alert>
      )}

      <Tabs defaultValue="contacts" className="gap-4">
        <TabsList className="flex h-auto w-fit flex-wrap">
          <TabsTrigger value="contacts">Contacts</TabsTrigger>
          <TabsTrigger value="lead-groups">Lead Groups</TabsTrigger>
          <TabsTrigger value="import">Import</TabsTrigger>
        </TabsList>

        <TabsContent value="contacts">
          <Card>
            <CardHeader>
              <CardTitle>Lead pool</CardTitle>
              <CardDescription>Search, filter, and review leads available for campaigns and sequences.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <div className="relative min-w-72 flex-1">
                  <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void loadContacts(search)
                    }}
                    className="pl-9"
                    placeholder="Search leads"
                  />
                </div>
                <Button variant="outline" onClick={() => void loadContacts(search)} disabled={loadingContacts}>
                  <RefreshCw className={`mr-2 size-4 ${loadingContacts ? "animate-spin" : ""}`} />
                  Refresh
                </Button>
              </div>

              <div className="grid gap-3 md:grid-cols-4">
                <FilterSelect
                  id="contact-industry-filter"
                  label="Industry"
                  value={industryFilter}
                  values={uniqueValues("industry")}
                  onChange={(value) => {
                    setIndustryFilter(value)
                    setPage(1)
                  }}
                />
                <FilterSelect
                  id="contact-title-filter"
                  label="Title"
                  value={titleFilter}
                  values={uniqueValues("title")}
                  onChange={(value) => {
                    setTitleFilter(value)
                    setPage(1)
                  }}
                />
                <FilterSelect
                  id="contact-interest-filter"
                  label="Product interest"
                  value={interestFilter}
                  values={uniqueValues("product_interest")}
                  onChange={(value) => {
                    setInterestFilter(value)
                    setPage(1)
                  }}
                />
                <FilterSelect
                  id="contact-source-filter"
                  label="Source"
                  value={sourceFilter}
                  values={uniqueValues("source")}
                  onChange={(value) => {
                    setSourceFilter(value)
                    setPage(1)
                  }}
                />
              </div>

              <div className="flex justify-end">
                <Button type="button" variant="ghost" size="sm" onClick={resetFilters}>
                  Clear filters
                </Button>
              </div>

              <ContactTable contacts={pagedContacts} />

              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href="#"
                      onClick={(event) => {
                        event.preventDefault()
                        setPage((current) => Math.max(1, current - 1))
                      }}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <span className="px-3 text-sm text-muted-foreground">Page {page} of {pageCount}</span>
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      onClick={(event) => {
                        event.preventDefault()
                        setPage((current) => Math.min(pageCount, current + 1))
                      }}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lead-groups">
          <Card>
            <CardHeader>
              <CardTitle>
                <h2>Lead Groups</h2>
              </CardTitle>
              <CardDescription>Reusable client-side lead groups based on available contact fields.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {leadGroups.map((group) => {
                const matchingCount = contacts.filter((contact) => matchesLeadGroup(contact, group)).length
                return (
                  <Link
                    key={group.id}
                    to="/contacts"
                    search={{ leadGroupId: group.id }}
                    className="rounded-md border bg-background p-4 transition hover:bg-muted/60"
                  >
                    <div className="font-medium">{group.name}</div>
                    <p className="mt-1 text-sm text-muted-foreground">{group.description}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="secondary">{matchingCount} matching</Badge>
                      {group.criteria.map((criterion) => (
                        <Badge
                          key={`${group.id}-${criterion.field}-${criterion.operator}-${criterion.value || "exists"}`}
                          variant="outline"
                        >
                          {criterionLabel(criterion)}
                        </Badge>
                      ))}
                    </div>
                  </Link>
                )
              })}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="import">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Import leads</CardTitle>
                <CardDescription>Email is required. Phone enables voice outreach.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                <div className="grid gap-2">
                  <Label htmlFor="contactCsv">CSV file</Label>
                  <Input id="contactCsv" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} />
                </div>
                <Button onClick={analyzeCsv} disabled={!file || busy}>
                  {busy ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Upload className="mr-2 size-4" />}
                  Analyze
                </Button>
              </CardContent>
            </Card>

            {importResult && (
              <Card>
                <CardHeader>
                  <CardTitle>Field mapping</CardTitle>
                  <CardDescription>{mappedFields} of {canonicalFields.length} fields mapped</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {canonicalFields.map((field) => (
                      <div key={field} className="grid gap-1.5">
                        <Label>{fieldLabels[field]}</Label>
                        <select
                          className="rounded-md border bg-background px-3 py-2 text-sm"
                          value={mapping[field] || ""}
                          onChange={(event) => setMapping((previous) => ({ ...previous, [field]: event.target.value }))}
                        >
                          <option value="">Not mapped</option>
                          {importResult.headers.map((header) => (
                            <option key={header} value={header}>{header}</option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <div>
                      <p className="mb-2 text-sm font-medium">Preview</p>
                      <div className="max-h-72 overflow-auto rounded-md border bg-muted/30 p-3">
                        {importResult.preview_rows.length === 0 ? (
                          <p className="py-8 text-center text-sm text-muted-foreground">No valid rows to preview.</p>
                        ) : (
                          <div className="space-y-2 text-xs">
                            {importResult.preview_rows.slice(0, 10).map((row) => (
                              <pre key={row.row_number} className="rounded bg-background p-2">{JSON.stringify(row.data, null, 2)}</pre>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    <div>
                      <p className="mb-2 text-sm font-medium">Validation</p>
                      <div className="max-h-72 overflow-auto rounded-md border bg-muted/30 p-3">
                        {importResult.errors.length === 0 ? (
                          <p className="py-8 text-center text-sm text-muted-foreground">No validation issues.</p>
                        ) : (
                          <ul className="space-y-2 text-sm">
                            {importResult.errors.slice(0, 10).map((error, index) => (
                              <li key={`${error.row_number}-${error.column}-${index}`}>
                                <Badge variant="outline" className="mr-2">Row {error.row_number}</Badge>
                                {error.column}: {error.message}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={importContacts} disabled={!file || busy || !mapping.email}>
                      {busy ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Users className="mr-2 size-4" />}
                      Import contacts
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function FilterSelect({
  id,
  label,
  value,
  values,
  onChange,
}: {
  id: string
  label: string
  value: string
  values: string[]
  onChange: (value: string) => void
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        className="h-10 rounded-md border bg-background px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="all">All {label.toLowerCase()}</option>
        {values.map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
      </select>
    </div>
  )
}

function ContactTable({ contacts }: { contacts: Contact[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Email</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Company</TableHead>
          <TableHead>Title</TableHead>
          <TableHead>Product interest</TableHead>
          <TableHead>Phone</TableHead>
          <TableHead>Timezone</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {contacts.length === 0 ? (
          <TableRow>
            <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
              No contacts found.
            </TableCell>
          </TableRow>
        ) : (
          contacts.map((contact) => (
            <TableRow key={contact.id}>
              <TableCell className="font-medium">{contact.email}</TableCell>
              <TableCell>{contactName(contact)}</TableCell>
              <TableCell>{contact.company || "-"}</TableCell>
              <TableCell>{contact.title || "-"}</TableCell>
              <TableCell>{contact.product_interest || "-"}</TableCell>
              <TableCell>{contact.phone || "-"}</TableCell>
              <TableCell>{contact.timezone || "UTC"}</TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
