import {
  ArrowUpRight,
  BadgeDollarSign,
  BarChart3,
  Bot,
  Compass,
  Handshake,
  Megaphone,
  ReceiptText,
  UsersRound,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { WorkspacePage } from "@/components/workspace/WorkspacePage"
import useAuth from "@/hooks/useAuth"

type WorkspaceCard = {
  title: string
  stage: string
  description: string
  href: string
  action: string
  icon: typeof Megaphone
  roles: string[]
}

const salesOpsUrl = import.meta.env.VITE_ECRM_APP_URL ?? "http://localhost:3000"

const workspaces: WorkspaceCard[] = [
  {
    title: "Lead Discovery",
    stage: "Source & Discover",
    description:
      "Firmographic search, internal AI entity resolution, fit scoring, and waterfall enrichment.",
    href: "/lead-discovery",
    action: "Open Lead Discovery",
    icon: Compass,
    roles: ["marketing", "engagement", "sdr", "sales", "sales_leader", "revops", "admin"],
  },
  {
    title: "EngageHub",
    stage: "Capture",
    description:
      "Campaigns, multilingual outreach, voice, email, and scheduling.",
    href: "/campaigns",
    action: "Open EngageHub",
    icon: Megaphone,
    roles: ["marketing", "engagement", "sdr", "sales", "admin"],
  },
  {
    title: "ChatHub",
    stage: "Capture",
    description:
      "Inbound chat, channels, knowledge, escalation, and inbox coverage.",
    href: "/chatbot/inbox",
    action: "Open ChatHub",
    icon: Bot,
    roles: ["engagement", "sdr", "sales", "admin"],
  },
  {
    title: "Sales Ops",
    stage: "Qualify & Pipeline",
    description:
      "Lead scoring, rep queues, pipeline, and margin-aware proposals.",
    href: salesOpsUrl,
    action: "Open Sales Ops",
    icon: Handshake,
    roles: ["sales", "sales_leader", "revops", "admin"],
  },
  {
    title: "Operations",
    stage: "Fulfill & Get Paid",
    description:
      "Order status, delivery exceptions, and customer commitments tied to the deal.",
    href: `${salesOpsUrl}/production`,
    action: "Open Operations",
    icon: ReceiptText,
    roles: ["operations", "sales_leader", "admin"],
  },
  {
    title: "Finance",
    stage: "Fulfill & Get Paid",
    description:
      "Company revenue, margin, collections, receivables, and incentive liability.",
    href: `${salesOpsUrl}/finance`,
    action: "Open Finance",
    icon: BadgeDollarSign,
    roles: ["finance", "admin"],
  },
  {
    title: "Performance",
    stage: "Incentives & Performance",
    description:
      "Targets, incentives, conversion health, and board-ready reporting.",
    href: `${salesOpsUrl}/performance`,
    action: "Open Performance",
    icon: BarChart3,
    roles: [
      "sales_leader",
      "revops",
      "finance",
      "compensation_admin",
      "executive",
      "admin",
    ],
  },
  {
    title: "Platform administration",
    stage: "Governance",
    description:
      "Users, roles, integrations, audit history, and approval controls.",
    href: "/admin",
    action: "Open administration",
    icon: UsersRound,
    roles: ["admin", "platform_admin"],
  },
]

function canOpen(
  card: WorkspaceCard,
  user: { is_superuser?: boolean; role?: string | null } | null | undefined,
) {
  return Boolean(
    user?.is_superuser || (user?.role && card.roles.includes(user.role)),
  )
}

export default function RevenueOsHomePage() {
  const { user } = useAuth()
  const visibleWorkspaces = workspaces.filter((card) => canOpen(card, user))

  return (
    <WorkspacePage
      eyebrow="ARA Global"
      icon={BarChart3}
      title="Revenue OS"
      description="One customer record. One operating rhythm."
      note="Reach, qualify, close, fulfill, get paid, and improve performance without handing customer context from one disconnected tool to another."
    >
      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Your workspaces</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Each workspace owns a clear stage of the revenue lifecycle.
              High-impact actions remain governed and auditable.
            </p>
          </div>
          <Badge variant="outline">
            {visibleWorkspaces.length} authorised areas
          </Badge>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {visibleWorkspaces.map((workspace) => {
            const Icon = workspace.icon
            const external = workspace.href.startsWith("http")
            return (
              <a
                className="workspace-link-card group"
                href={workspace.href}
                key={workspace.title}
                rel={external ? "noreferrer" : undefined}
                target={external ? "_blank" : undefined}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="rounded-xl border border-primary/20 bg-primary/10 p-2.5 text-primary transition-transform duration-200 group-hover:scale-105">
                    <Icon className="size-5" />
                  </div>
                  <Badge variant="secondary" className="text-[10px] font-semibold uppercase tracking-wider">
                    {workspace.stage}
                  </Badge>
                </div>
                <h3 className="mt-4 text-base font-bold tracking-tight text-foreground sm:text-lg">
                  {workspace.title}
                </h3>
                <p className="mt-2 min-h-12 flex-1 text-xs leading-relaxed text-muted-foreground">
                  {workspace.description}
                </p>
                <span className="mt-5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary transition-all duration-150 group-hover:gap-2">
                  {workspace.action}
                  <ArrowUpRight className="size-3.5" />
                </span>
              </a>
            )
          })}
        </div>
      </section>

      <section className="relative overflow-hidden rounded-2xl border border-border/80 bg-gradient-to-r from-card via-card to-primary/5 p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] font-semibold uppercase tracking-wider border-primary/30 text-primary">
            Autonomous Engine
          </Badge>
        </div>
        <h2 className="mt-2 text-base font-bold tracking-tight text-foreground sm:text-lg">
          Agent workforce
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground sm:text-sm">
          Capture: Outreach, Campaign &amp; Funnel, Chat &amp; Bot. Qualify: Lead
          Scoring, Pipeline, Proposal. Fulfill: Order Tracking, Payment, ERP
          Sync. Performance: Incentive, Target Tracking, Analytics.
        </p>
      </section>
    </WorkspacePage>
  )
}
