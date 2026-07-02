import { Link } from "@tanstack/react-router"
import { ArrowRight, Plus, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import WorkspaceHeader from "@/components/layout/WorkspaceHeader"
import {
  campaignLifecycleOrder,
  formatCampaignDate,
  getCampaignLifecycleLabel,
  getCampaignLifecycleMeta,
  getCampaignLifecycleRoute,
  getCampaignLifecycleTone,
  useCampaignsWorkspace,
} from "./campaign-data"
import { cn } from "@/lib/utils"

const toneClasses = {
  info: "bg-primary/10 text-primary",
  ready: "bg-[color:var(--workspace-success)]/10 text-[var(--workspace-success)]",
  warning:
    "bg-[color:var(--workspace-warning)]/10 text-[var(--workspace-warning)]",
} as const

export default function CampaignsWorkspacePage() {
  const { campaigns, count, counts, loading, error, refresh } =
    useCampaignsWorkspace()

  const recentCampaigns = campaigns.slice(0, 6)

  return (
    <div className="flex flex-col gap-6">
      <WorkspaceHeader
        eyebrow="Campaigns"
        title="Campaign lifecycle"
        description="Use the lifecycle lanes to keep draft work, live activity, and paused work separated the way operators actually work."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/campaigns/draft">
                <Plus className="size-4" />
                New draft
              </Link>
            </Button>
            <Button variant="outline" onClick={refresh} disabled={loading}>
              <RefreshCw className={cn("size-4", loading && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      {error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="py-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-3 md:grid-cols-3">
        {campaignLifecycleOrder.map((status) => {
          const meta = getCampaignLifecycleMeta(status)
          const tone = toneClasses[getCampaignLifecycleTone(status)]

          return (
            <Card key={status} className="border-border/70">
              <CardHeader className="flex flex-row items-center justify-between gap-3 pb-2">
                <div>
                  <CardDescription className="text-xs font-semibold uppercase tracking-wide">
                    {meta.label}
                  </CardDescription>
                  <CardTitle className="mt-2 text-lg">{meta.title}</CardTitle>
                </div>
                <Badge variant="outline" className={tone}>
                  {counts[status]}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{meta.description}</p>
                <Button asChild variant="outline" size="sm">
                  <Link to={getCampaignLifecycleRoute(status)}>
                    Open {getCampaignLifecycleLabel(status)}
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Recent campaigns</CardTitle>
          <CardDescription>
            {count} campaign{count === 1 ? "" : "s"} in the workspace.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {recentCampaigns.length === 0 ? (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground md:col-span-2 xl:col-span-3">
                No campaigns are available yet.
              </div>
            ) : (
              recentCampaigns.map((campaign) => {
                const status = campaign.status
                const meta = getCampaignLifecycleMeta(
                  status === "draft" || status === "active" || status === "paused"
                    ? status
                    : "draft",
                )
                return (
                  <div
                    key={campaign.id}
                    className="rounded-md border border-border/70 bg-[var(--workspace-surface)] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-foreground">
                          {campaign.name}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {formatCampaignDate(campaign.created_at)}
                        </p>
                      </div>
                      <Badge variant="outline">
                        {getCampaignLifecycleLabel(
                          status === "draft" || status === "active" || status === "paused"
                            ? status
                            : "draft",
                        )}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">
                      {meta.nextStep}
                    </p>
                  </div>
                )
              })
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
