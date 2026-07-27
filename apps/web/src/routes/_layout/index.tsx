import { Link, createFileRoute } from "@tanstack/react-router"
import {
  Activity,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  CircleAlert,
  DatabaseZap,
  FileText,
  ListChecks,
  Mail,
  Mic2,
  PlugZap,
  ShieldCheck,
  Users,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import WorkspaceHeader from "@/components/layout/WorkspaceHeader"
import { Button } from "@/components/ui/button"
import RevenueOsHomePage from "@/features/revenue-os/RevenueOsHomePage"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"

type Tone = "info" | "ready" | "warning" | "danger"

type DashboardItem = {
  icon: LucideIcon
  title: string
  detail: string
  status?: string
  path?: string
  cta?: string
  tone: Tone
}

const toneStyles: Record<
  Tone,
  { icon: string; panel: string; badge: string; marker: string }
> = {
  info: {
    icon: "bg-primary/10 text-primary",
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-primary/10 text-primary",
    marker: "bg-primary",
  },
  ready: {
    icon: "bg-[color:var(--workspace-success)]/10 text-[var(--workspace-success)]",
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-[color:var(--workspace-success)]/10 text-[var(--workspace-success)]",
    marker: "bg-[var(--workspace-success)]",
  },
  warning: {
    icon: "bg-[color:var(--workspace-warning)]/10 text-[var(--workspace-warning)]",
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-[color:var(--workspace-warning)]/10 text-[var(--workspace-warning)]",
    marker: "bg-[var(--workspace-warning)]",
  },
  danger: {
    icon: "bg-[color:var(--workspace-danger)]/10 text-[var(--workspace-danger)]",
    panel: "bg-[var(--workspace-surface)]",
    badge: "bg-[color:var(--workspace-danger)]/10 text-[var(--workspace-danger)]",
    marker: "bg-[var(--workspace-danger)]",
  },
}

const signalCards: DashboardItem[] = [
  {
    icon: DatabaseZap,
    title: "Campaign signals",
    detail: "Live activity rollups appear here after campaign events are connected.",
    status: "Waiting for data",
    tone: "info",
  },
  {
    icon: Building2,
    title: "Account context",
    detail: "Customer 360 is available for account and contact inspection.",
    status: "Ready to review",
    tone: "ready",
  },
  {
    icon: PlugZap,
    title: "Provider readiness",
    detail: "Review provider settings before launching outbound work.",
    status: "Needs review",
    tone: "warning",
  },
  {
    icon: ShieldCheck,
    title: "Governance",
    detail: "Use controls and admin settings to keep access aligned.",
    status: "Configured in app",
    tone: "ready",
  },
]

const priorityQueue: DashboardItem[] = [
  {
    icon: PlugZap,
    title: "Review provider readiness",
    detail: "Confirm voice and email providers before teams add more campaign volume.",
    path: "/settings/providers",
    cta: "Open providers",
    tone: "warning",
  },
  {
    icon: Building2,
    title: "Work from Customer 360",
    detail: "Start from account context when deciding whether email, voice, or chat should go next.",
    path: "/customer-360",
    cta: "View accounts",
    tone: "ready",
  },
  {
    icon: FileText,
    title: "Prepare reusable content",
    detail: "Review templates before attaching messages to campaigns and sequences.",
    path: "/templates",
    cta: "Open templates",
    tone: "info",
  },
]

const healthItems: DashboardItem[] = [
  {
    icon: CheckCircle2,
    title: "Session",
    detail: "Authenticated workspace session is active.",
    status: "Online",
    tone: "ready",
  },
  {
    icon: CircleAlert,
    title: "Live dashboard feed",
    detail: "Campaign metrics are not wired into this landing surface yet.",
    status: "Not connected",
    tone: "warning",
  },
  {
    icon: Activity,
    title: "Activity stream",
    detail: "Recent movement will show here when event ingestion is connected.",
    status: "No feed",
    tone: "info",
  },
]

const quickAccess = [
  {
    icon: ListChecks,
    title: "Campaigns",
    description: "Create and inspect campaign work.",
    path: "/campaigns",
  },
  {
    icon: Mail,
    title: "Sequences",
    description: "Build drip and follow-up paths.",
    path: "/sequences",
  },
  {
    icon: Mic2,
    title: "Voice Agents",
    description: "Tune voice agent scripts, personas, and setup.",
    path: "/voice-agents",
  },
  {
    icon: BarChart3,
    title: "Analytics",
    description: "Open reporting once data is connected.",
    path: "/analytics",
  },
  {
    icon: Users,
    title: "Contacts",
    description: "Review people and account links.",
    path: "/contacts",
  },
]

export const Route = createFileRoute("/_layout/")({
  component: RevenueOsHomePage,
  head: () => ({
    meta: [{ title: "Revenue OS - ARA Global" }],
  }),
})

function StatusBadge({ item }: { item: DashboardItem }) {
  if (!item.status) return null

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-1 text-xs font-medium",
        toneStyles[item.tone].badge,
      )}
    >
      {item.status}
    </span>
  )
}

export function Dashboard() {
  const { user: currentUser } = useAuth()
  const firstName =
    currentUser?.full_name?.split(" ")[0] ||
    currentUser?.email?.split("@")[0] ||
    "there"

  return (
    <div className="flex flex-col gap-5">
      <WorkspaceHeader
        eyebrow="Dashboard"
        title="Campaign control at a glance"
        description={`${firstName}, use this surface to move from setup checks into account and campaign work without losing channel context.`}
        actions={
          <>
            <Button asChild>
              <Link to="/campaigns">
                Open campaigns
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/customer-360">Customer 360</Link>
            </Button>
          </>
        }
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {signalCards.map((item) => {
          const Icon = item.icon

          return (
            <div
              key={item.title}
              className={cn(
                "rounded-md border border-[var(--workspace-border)] p-4 shadow-[0_16px_36px_-30px_rgba(22,53,81,0.55)]",
                toneStyles[item.tone].panel,
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div
                  className={cn(
                    "flex size-9 items-center justify-center rounded-md",
                    toneStyles[item.tone].icon,
                  )}
                >
                  <Icon className="size-4" />
                </div>
                <StatusBadge item={item} />
              </div>
              <h2 className="mt-4 text-sm font-semibold text-foreground">
                {item.title}
              </h2>
              <p className="mt-2 text-sm leading-5 text-muted-foreground">
                {item.detail}
              </p>
            </div>
          )
        })}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="rounded-md border border-[var(--workspace-border)] bg-[var(--workspace-surface)] p-4 shadow-[0_18px_44px_-34px_rgba(22,53,81,0.55)] sm:p-5">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-primary">
                Active work
              </p>
              <h2 className="mt-1 text-xl font-semibold text-foreground">
                Priority queue
              </h2>
            </div>
            <p className="max-w-md text-sm text-muted-foreground">
              Starter work is shown until live campaign signals are connected.
            </p>
          </div>

          <div className="mt-5 divide-y divide-border/70">
            {priorityQueue.map((item) => {
              const Icon = item.icon

              return (
                <div
                  key={item.title}
                  className="grid gap-4 py-4 first:pt-0 last:pb-0 md:grid-cols-[auto_minmax(0,1fr)_auto] md:items-center"
                >
                  <div
                    className={cn(
                      "flex size-10 items-center justify-center rounded-md",
                      toneStyles[item.tone].icon,
                    )}
                  >
                    <Icon className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-foreground">
                      {item.title}
                    </h3>
                    <p className="mt-1 text-sm leading-5 text-muted-foreground">
                      {item.detail}
                    </p>
                  </div>
                  {item.path && item.cta ? (
                    <Button asChild variant="outline" size="sm">
                      <Link to={item.path as never}>
                        {item.cta}
                        <ArrowRight className="size-4" />
                      </Link>
                    </Button>
                  ) : null}
                </div>
              )
            })}
          </div>
        </section>

        <aside className="flex flex-col gap-5">
          <section className="rounded-md border border-[var(--workspace-border)] bg-[var(--workspace-surface)] p-4 shadow-[0_18px_44px_-34px_rgba(22,53,81,0.55)]">
            <div>
              <p className="text-xs font-semibold uppercase text-primary">
                Readiness
              </p>
              <h2 className="mt-1 text-lg font-semibold text-foreground">
                System health
              </h2>
            </div>
            <div className="mt-4 flex flex-col gap-3">
              {healthItems.map((item) => {
                const Icon = item.icon

                return (
                  <div key={item.title} className="flex gap-3">
                    <span
                      className={cn(
                        "mt-1 size-2 rounded-full",
                        toneStyles[item.tone].marker,
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Icon className="size-4 text-muted-foreground" />
                          <h3 className="text-sm font-medium text-foreground">
                            {item.title}
                          </h3>
                        </div>
                        <StatusBadge item={item} />
                      </div>
                      <p className="mt-1 text-sm leading-5 text-muted-foreground">
                        {item.detail}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="rounded-md border border-[var(--workspace-border)] bg-[var(--workspace-panel)] p-4">
            <p className="text-sm font-semibold text-foreground">
              Recent movement
            </p>
            <p className="mt-2 text-sm leading-5 text-muted-foreground">
              Connect campaign and channel events to populate this rail with
              real account movement.
            </p>
          </section>
        </aside>
      </div>

      <section className="rounded-md border border-[var(--workspace-border)] bg-[var(--workspace-surface)] p-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <p className="text-sm font-semibold text-foreground">Quick access</p>
          <p className="text-sm text-muted-foreground">
            Secondary navigation for common workspace surfaces.
          </p>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {quickAccess.map((item) => {
            const Icon = item.icon

            return (
              <Link
                key={item.title}
                to={item.path as never}
                className="group rounded-md border border-border/80 bg-[var(--workspace-surface-muted)] p-3 transition hover:border-primary/50 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <div className="flex items-center gap-2">
                  <Icon className="size-4 text-primary" />
                  <span className="text-sm font-semibold text-foreground">
                    {item.title}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-5 text-muted-foreground">
                  {item.description}
                </p>
              </Link>
            )
          })}
        </div>
      </section>
    </div>
  )
}
