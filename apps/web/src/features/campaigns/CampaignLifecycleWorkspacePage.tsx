import { Link } from "@tanstack/react-router"
import { Loader2, PauseCircle, PlayCircle, RefreshCw, ArrowRight } from "lucide-react"
import { useMemo, useState } from "react"

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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import WorkspaceHeader from "@/components/layout/WorkspaceHeader"
import { cn } from "@/lib/utils"
import { signalloopRequest } from "@/lib/signalloop-api"
import {
  campaignLifecycleOrder,
  formatCampaignDate,
  getCampaignLifecycleDescription,
  getCampaignLifecycleLabel,
  getCampaignLifecycleMeta,
  getCampaignLifecycleNextStep,
  getCampaignLifecycleRoute,
  getCampaignLifecycleTitle,
  getCampaignLifecycleTone,
  normalizeCampaignStatus,
  type CampaignLifecycleStatus,
  useCampaignsWorkspace,
} from "./campaign-data"
import CampaignIntakeWizardPage from "./CampaignIntakeWizardPage"

type CampaignLifecycleWorkspacePageProps = {
  statusFilter: CampaignLifecycleStatus | "all"
  showBuilder?: boolean
}

const toneClasses: Record<
  "info" | "ready" | "warning",
  { panel: string; badge: string; marker: string }
> = {
  info: {
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-primary/10 text-primary",
    marker: "bg-primary",
  },
  ready: {
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-[color:var(--workspace-success)]/10 text-[var(--workspace-success)]",
    marker: "bg-[var(--workspace-success)]",
  },
  warning: {
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-[color:var(--workspace-warning)]/10 text-[var(--workspace-warning)]",
    marker: "bg-[var(--workspace-warning)]",
  },
}

function statusBadgeVariant(status: CampaignLifecycleStatus) {
  if (status === "active") {
    return "default" as const
  }
  if (status === "paused") {
    return "secondary" as const
  }
  return "outline" as const
}

function actionLabel(status: CampaignLifecycleStatus) {
  if (status === "active") return "Pause"
  if (status === "paused") return "Resume"
  return "Open draft"
}

function nextStep(status: CampaignLifecycleStatus) {
  return getCampaignLifecycleNextStep(status)
}

export default function CampaignLifecycleWorkspacePage({
  statusFilter,
  showBuilder = false,
}: CampaignLifecycleWorkspacePageProps) {
  const { campaigns, count, counts, loading, error, refresh, setError } =
    useCampaignsWorkspace()
  const [busyCampaignId, setBusyCampaignId] = useState<string | null>(null)

  const visibleCampaigns = useMemo(() => {
    const normalized = campaigns.filter((campaign) =>
      normalizeCampaignStatus(campaign.status),
    )

    if (statusFilter === "all") {
      return normalized
    }

    return normalized.filter(
      (campaign) => normalizeCampaignStatus(campaign.status) === statusFilter,
    )
  }, [campaigns, statusFilter])

  const statusCards = campaignLifecycleOrder.map((status) => {
    const meta = getCampaignLifecycleMeta(status)
    const tone = toneClasses[getCampaignLifecycleTone(status)]
    const isActive = statusFilter === status

    return {
      status,
      meta,
      tone,
      isActive,
      count: counts[status],
    }
  })

  const transitionCampaign = async (
    campaignId: string,
    transition: "pause" | "resume",
  ) => {
    setBusyCampaignId(campaignId)
    setError("")

    try {
      await signalloopRequest(`/api/v1/campaigns/${campaignId}/${transition}`, {
        method: "PUT",
        idempotent: true,
      })
      refresh()
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not update campaign",
      )
    } finally {
      setBusyCampaignId(null)
    }
  }

  const title =
    statusFilter === "all"
      ? "Campaign lifecycle"
      : getCampaignLifecycleTitle(statusFilter)

  const description =
    statusFilter === "all"
      ? "Status-first campaign workspace with a draft builder, a running queue, and simple pause/resume controls."
      : getCampaignLifecycleDescription(statusFilter)

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        eyebrow="Campaigns"
        title={title}
        description={description}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/campaigns">
                Overview
              </Link>
            </Button>
            <Button asChild>
              <Link to="/campaigns/draft">
                Drafts
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </>
        }
      />

      {error ? (
        <Alert variant="destructive">
          <p className="text-sm">{error}</p>
        </Alert>
      ) : null}

      <section className="grid gap-3 md:grid-cols-3">
        {statusCards.map((card) => (
          <Link
            key={card.status}
            to={getCampaignLifecycleRoute(card.status)}
            className={cn(
              "rounded-md border p-4 transition hover:border-primary/50 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              card.isActive && "border-primary/50 bg-primary/5",
              card.tone.panel,
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={cn("size-2 rounded-full", card.tone.marker)} />
                  <p className="text-xs font-semibold uppercase text-muted-foreground">
                    {card.meta.label}
                  </p>
                </div>
                <h2 className="mt-2 text-lg font-semibold text-foreground">
                  {card.meta.title}
                </h2>
              </div>
              <Badge variant={card.isActive ? "default" : "outline"}>
                {card.count}
              </Badge>
            </div>
            <p className="mt-2 text-sm leading-5 text-muted-foreground">
              {card.meta.description}
            </p>
          </Link>
        ))}
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>
                {statusFilter === "all"
                  ? "Campaign list"
                  : `${getCampaignLifecycleLabel(statusFilter)} campaigns`}
              </CardTitle>
              <CardDescription>
                {statusFilter === "all"
                  ? `${count} campaigns in the workspace.`
                  : `${visibleCampaigns.length} campaign${visibleCampaigns.length === 1 ? "" : "s"} in this state.`}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={refresh}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Next step</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && visibleCampaigns.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="py-10 text-center text-muted-foreground"
                  >
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" />
                      Loading campaigns...
                    </span>
                  </TableCell>
                </TableRow>
              ) : visibleCampaigns.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="py-10 text-center text-muted-foreground"
                  >
                    {statusFilter === "draft"
                      ? "No draft campaigns yet. Use the builder below to start one."
                      : "No campaigns found in this lifecycle state."}
                  </TableCell>
                </TableRow>
              ) : (
                visibleCampaigns.map((campaign) => {
                  const lifecycleStatus =
                    normalizeCampaignStatus(campaign.status) ?? "draft"
                  const action = actionLabel(lifecycleStatus)
                  const rowKey = campaign.id
                  const next = nextStep(lifecycleStatus)

                  return (
                    <TableRow key={rowKey}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{campaign.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {campaign.id}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(lifecycleStatus)}>
                          {getCampaignLifecycleLabel(lifecycleStatus)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatCampaignDate(campaign.created_at)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {next}
                      </TableCell>
                      <TableCell className="text-right">
                        {lifecycleStatus === "active" ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void transitionCampaign(campaign.id, "pause")}
                            disabled={busyCampaignId === campaign.id}
                            className="gap-2"
                          >
                            {busyCampaignId === campaign.id ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <PauseCircle className="size-4" />
                            )}
                            {action}
                          </Button>
                        ) : lifecycleStatus === "paused" ? (
                          <Button
                            size="sm"
                            onClick={() => void transitionCampaign(campaign.id, "resume")}
                            disabled={busyCampaignId === campaign.id}
                            className="gap-2"
                          >
                            {busyCampaignId === campaign.id ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <PlayCircle className="size-4" />
                            )}
                            {action}
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" asChild>
                            <Link to="/campaigns/draft" className="gap-2">
                              <ArrowRight className="size-4" />
                              {action}
                            </Link>
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {showBuilder ? (
        <Card id="campaign-draft-builder">
          <CardHeader>
            <CardTitle>Campaign draft builder</CardTitle>
            <CardDescription>
              Draft campaigns start here. Keep the builder below the list so the
              workspace still reads like an operating queue.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CampaignIntakeWizardPage />
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
