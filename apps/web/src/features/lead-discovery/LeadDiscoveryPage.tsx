import {
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Compass,
  Cpu,
  Flame,
  Globe,
  Loader2,
  Mail,
  Phone,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  UserPlus,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { WorkspacePage } from "@/components/workspace/WorkspacePage"
import {
  type DiscoveredLead,
  type DiscoverySearchCriteria,
  type EnrichmentResponse,
  enrichLeadEntity,
  promoteDiscoveredLead,
  searchDiscoveredLeads,
} from "@/features/lead-discovery/api"

const SAMPLE_INDUSTRIES = [
  "Technology & SaaS",
  "Fintech & Payments",
  "Healthcare & Life Sciences",
  "E-Commerce & Retail",
  "Logistics & Supply Chain",
]

const INITIAL_CRITERIA: DiscoverySearchCriteria = {
  industries: ["Technology & SaaS"],
  job_titles: ["VP of Sales"],
  employee_min: 50,
  employee_max: 500,
  countries: ["United States"],
  tech_stack: ["Salesforce"],
  limit: 15,
}

export default function LeadDiscoveryPage() {
  const [industry, setIndustry] = useState("Technology & SaaS")
  const [jobTitle, setJobTitle] = useState("VP of Sales")
  const [employeeMin, setEmployeeMin] = useState<number>(50)
  const [employeeMax, setEmployeeMax] = useState<number>(500)
  const [country, setCountry] = useState("United States")
  const [techStack, setTechStack] = useState("Salesforce")

  const [isLoading, setIsLoading] = useState(false)
  const [leads, setLeads] = useState<DiscoveredLead[]>([])
  const [error, setError] = useState<string | null>(null)
  const [expandedLeadId, setExpandedLeadId] = useState<string | null>(null)

  // Promotion state
  const [promotedIds, setPromotedIds] = useState<Set<string>>(new Set())
  const [promotingId, setPromotingId] = useState<string | null>(null)

  // Enrichment modal state
  const [enrichingId, setEnrichingId] = useState<string | null>(null)
  const [enrichedData, setEnrichedData] = useState<EnrichmentResponse | null>(
    null,
  )
  const [isModalOpen, setIsModalOpen] = useState(false)

  const search = useCallback(async (criteria: DiscoverySearchCriteria) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await searchDiscoveredLeads(criteria)
      setLeads(response.leads)
      if (response.leads.length > 0) {
        setExpandedLeadId((current) => current ?? response.leads[0].id)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to search leads")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void search(INITIAL_CRITERIA)
  }, [search])

  const handleSearch = () =>
    search({
      industries: industry ? [industry] : [],
      job_titles: jobTitle ? [jobTitle] : [],
      employee_min: employeeMin || undefined,
      employee_max: employeeMax || undefined,
      countries: country ? [country] : [],
      tech_stack: techStack ? [techStack] : [],
      limit: 15,
    })

  const handlePromote = async (lead: DiscoveredLead) => {
    setPromotingId(lead.id)
    try {
      await promoteDiscoveredLead({
        lead_id: lead.id,
        tags: [
          "ai-discovered",
          "waterfall-enriched",
          lead.fit_band.toLowerCase(),
        ],
      })
      setPromotedIds((prev) => new Set(prev).add(lead.id))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to promote lead")
    } finally {
      setPromotingId(null)
    }
  }

  const handleEnrich = async (lead: DiscoveredLead) => {
    setEnrichingId(lead.id)
    try {
      const res = await enrichLeadEntity({
        domain: lead.company_domain,
        company_name: lead.company_name,
        email: lead.email,
      })
      setEnrichedData(res)
      setIsModalOpen(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Enrichment lookup failed")
    } finally {
      setEnrichingId(null)
    }
  }

  const metrics = useMemo(() => {
    const total = leads.length
    const hot = leads.filter((l) => l.fit_band === "HOT_OPPORTUNITY").length
    const high = leads.filter((l) => l.fit_band === "HIGH_FIT").length
    const avgScore = total
      ? Math.round(leads.reduce((acc, curr) => acc + curr.fit_score, 0) / total)
      : 0
    return { total, hot, high, avgScore }
  }, [leads])

  return (
    <WorkspacePage
      eyebrow="Accounts"
      icon={Compass}
      title="Lead Discovery"
      description="Source high-fit B2B prospects, resolve entities against existing accounts, and synthesize tailored conversation starters."
      metrics={[
        { label: "Discovered leads", value: metrics.total, icon: Compass },
        {
          label: "Hot opportunities",
          value: metrics.hot,
          icon: Flame,
          tone: "success",
        },
        {
          label: "High fit ICP",
          value: metrics.high,
          icon: Target,
          tone: "info",
        },
        {
          label: "Average AI score",
          value: (
            <>
              {metrics.avgScore}
              <span className="ml-1 text-xs font-normal text-muted-foreground">
                / 100
              </span>
            </>
          ),
          icon: TrendingUp,
        },
      ]}
    >
      {error && (
        <Alert
          variant="destructive"
          className="border-destructive/50 text-destructive"
        >
          {error}
        </Alert>
      )}

      {/* Search Criteria Matrix */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-base flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                Firmographic & Demographics Filter Matrix
              </CardTitle>
              <CardDescription className="text-xs">
                Refine lead criteria across industry, employee count, geography,
                and technologies.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Target Industry</Label>
              <Input
                placeholder="e.g. Technology & SaaS"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="h-9 text-xs"
              />
              <div className="flex flex-wrap gap-1 mt-1">
                {SAMPLE_INDUSTRIES.slice(0, 3).map((ind) => (
                  <button
                    key={ind}
                    type="button"
                    onClick={() => setIndustry(ind)}
                    className="text-[10px] text-muted-foreground hover:text-foreground underline"
                  >
                    {ind.split("&")[0]}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Target Job Title / Seniority</Label>
              <Input
                placeholder="e.g. VP of Sales, CTO"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Headcount Range (Min - Max)</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  placeholder="50"
                  value={employeeMin}
                  onChange={(e) => setEmployeeMin(Number(e.target.value))}
                  className="h-9 text-xs"
                />
                <span className="text-xs text-muted-foreground">-</span>
                <Input
                  type="number"
                  placeholder="500"
                  value={employeeMax}
                  onChange={(e) => setEmployeeMax(Number(e.target.value))}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Country / Region</Label>
              <Input
                placeholder="e.g. United States, California"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Tech Stack Signal</Label>
              <Input
                placeholder="e.g. Salesforce, AWS, Snowflake"
                value={techStack}
                onChange={(e) => setTechStack(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="flex items-end">
              <Button
                onClick={handleSearch}
                disabled={isLoading}
                className="w-full h-9 gap-2 text-xs font-semibold"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Querying Waterfall Providers...
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" />
                    Discover High-Fit Leads
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Discovered Leads List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Discovered Prospects ({leads.length})
          </h2>
          <span className="text-xs text-muted-foreground">
            Sorted by AI Fit Score & Intent Urgency
          </span>
        </div>

        {leads.length === 0 && !isLoading && (
          <Card className="p-8 text-center">
            <Compass className="mx-auto h-8 w-8 text-muted-foreground/50" />
            <p className="mt-2 text-sm text-muted-foreground">
              No leads discovered for the selected criteria. Adjust your search
              filters and try again.
            </p>
          </Card>
        )}

        {leads.map((lead) => {
          const isExpanded = expandedLeadId === lead.id
          const isPromoted = promotedIds.has(lead.id) || lead.is_promoted
          const isPromoting = promotingId === lead.id
          const isEnriching = enrichingId === lead.id

          return (
            <Card
              key={lead.id}
              className={`transition-all border ${
                lead.fit_band === "HOT_OPPORTUNITY"
                  ? "border-emerald-500/30 bg-emerald-500/[0.02]"
                  : "border-border/80"
              }`}
            >
              <div className="p-4 sm:p-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  {/* Left: Contact Info */}
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground text-base">
                        {lead.first_name} {lead.last_name}
                      </span>
                      <span className="text-xs text-muted-foreground">•</span>
                      <span className="text-xs font-medium text-foreground/80">
                        {lead.title || "Decision Maker"}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-[10px] uppercase font-bold tracking-wider ${
                          lead.fit_band === "HOT_OPPORTUNITY"
                            ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                            : lead.fit_band === "HIGH_FIT"
                              ? "border-blue-500/40 text-blue-600 dark:text-blue-400 bg-blue-500/10"
                              : "border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/10"
                        }`}
                      >
                        {lead.fit_band.replace("_", " ")}
                      </Badge>
                      {lead.match_confidence === "EXACT_MATCH" ? (
                        <Badge variant="secondary" className="text-[10px]">
                          Existing Account
                        </Badge>
                      ) : (
                        <Badge
                          variant="outline"
                          className="text-[10px] text-muted-foreground"
                        >
                          New Prospect
                        </Badge>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1 font-medium text-foreground">
                        <Building2 className="h-3.5 w-3.5 text-primary" />
                        {lead.company_name}
                        <span className="font-normal text-muted-foreground">
                          ({lead.company_domain})
                        </span>
                      </span>
                      <span className="flex items-center gap-1">
                        <Mail className="h-3.5 w-3.5" />
                        {lead.email}
                      </span>
                      {lead.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="h-3.5 w-3.5" />
                          {lead.phone}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Globe className="h-3.5 w-3.5" />
                        {lead.city}, {lead.region || lead.country}
                      </span>
                    </div>

                    {/* Tech Stack & Intent Signals */}
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      {lead.tech_stack.map((tech) => (
                        <span
                          key={tech}
                          className="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
                        >
                          <Cpu className="h-2.5 w-2.5" />
                          {tech}
                        </span>
                      ))}
                      {lead.intent_signals.map((sig) => (
                        <span
                          key={sig}
                          className="inline-flex items-center gap-1 rounded bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
                        >
                          <TrendingUp className="h-2.5 w-2.5" />
                          {sig}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Right: Score & Actions */}
                  <div className="flex items-center gap-3 sm:flex-col sm:items-end">
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-black text-foreground">
                        {lead.fit_score}
                      </span>
                      <span className="text-xs text-muted-foreground">pts</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleEnrich(lead)}
                        disabled={isEnriching}
                        className="h-8 gap-1 text-xs"
                      >
                        {isEnriching ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Sparkles className="h-3 w-3 text-primary" />
                        )}
                        Enrich
                      </Button>

                      <Button
                        size="sm"
                        onClick={() => handlePromote(lead)}
                        disabled={isPromoted || isPromoting}
                        variant={isPromoted ? "secondary" : "default"}
                        className="h-8 gap-1 text-xs"
                      >
                        {isPromoting ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : isPromoted ? (
                          <>
                            <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                            In CRM
                          </>
                        ) : (
                          <>
                            <UserPlus className="h-3 w-3" />
                            Promote to CRM
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Collapsible AI Opportunity Brief */}
                <div className="mt-3 pt-3 border-t border-border/50">
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedLeadId(isExpanded ? null : lead.id)
                    }
                    className="flex w-full items-center justify-between text-xs font-semibold text-primary hover:underline"
                  >
                    <span className="flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5" />
                      AI Opportunity Brief & Conversation Hooks
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" />
                    )}
                  </button>

                  {isExpanded && (
                    <div className="mt-3 space-y-2 rounded-lg bg-muted/40 p-3 text-xs">
                      <div>
                        <span className="font-semibold text-foreground">
                          Qualification Rationale:
                        </span>{" "}
                        <span className="text-muted-foreground">
                          {lead.score_rationale ||
                            "High ICP alignment based on firmographics and role authority."}
                        </span>
                      </div>

                      {lead.conversation_starters.length > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <span className="font-semibold text-foreground">
                            Personalized Outreach Angles:
                          </span>
                          <div className="space-y-1 pl-2">
                            {lead.conversation_starters.map((starter, sIdx) => (
                              <div
                                key={sIdx}
                                className="rounded bg-background p-2 border text-[11px] text-foreground/90 font-mono leading-relaxed"
                              >
                                {starter}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {/* Deep Enrichment Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Waterfall Deep Intelligence
            </DialogTitle>
            <DialogDescription className="text-xs">
              Live enrichment returned from internal intelligence & waterfall
              gateway.
            </DialogDescription>
          </DialogHeader>

          {enrichedData && (
            <div className="space-y-3 text-xs">
              <div>
                <span className="font-semibold text-foreground">Company:</span>{" "}
                {enrichedData.company_name} ({enrichedData.domain})
              </div>
              <div>
                <span className="font-semibold text-foreground">
                  Revenue Range:
                </span>{" "}
                {enrichedData.revenue_range || "N/A"}
              </div>
              <div>
                <span className="font-semibold text-foreground">
                  Headcount:
                </span>{" "}
                {enrichedData.employee_count} employees
              </div>

              <Separator />

              <div>
                <span className="font-semibold text-foreground">
                  Verified Tech Stack:
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {enrichedData.tech_stack.map((t) => (
                    <Badge key={t} variant="secondary" className="text-[10px]">
                      {t}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <span className="font-semibold text-foreground">
                  Key Decision Makers:
                </span>
                <div className="space-y-1 mt-1">
                  {enrichedData.key_contacts.map((c) => (
                    <div
                      key={c.email}
                      className="rounded border bg-muted/30 p-2"
                    >
                      <div className="font-semibold text-foreground">
                        {c.name}
                      </div>
                      <div className="text-muted-foreground">
                        {c.title} • {c.email}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </WorkspacePage>
  )
}
