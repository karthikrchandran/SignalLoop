import { ArrowUpRight, BadgeDollarSign, BarChart3, Bot, Handshake, Megaphone, ReceiptText, Target, UsersRound } from "lucide-react"

import { Badge } from "@/components/ui/badge"
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
  { title: "EngageHub", stage: "Capture", description: "Campaigns, multilingual outreach, voice, email, and scheduling.", href: "/campaigns", action: "Open EngageHub", icon: Megaphone, roles: ["marketing", "engagement", "sdr", "sales", "admin"] },
  { title: "ChatHub", stage: "Capture", description: "Inbound chat, channels, knowledge, escalation, and inbox coverage.", href: "/chatbot/inbox", action: "Open ChatHub", icon: Bot, roles: ["engagement", "sdr", "sales", "admin"] },
  { title: "Sales Ops", stage: "Qualify & Pipeline", description: "Lead scoring, rep queues, pipeline, and margin-aware proposals.", href: salesOpsUrl, action: "Open Sales Ops", icon: Handshake, roles: ["sales", "sales_leader", "revops", "admin"] },
  { title: "Operations", stage: "Fulfill & Get Paid", description: "Order status, delivery exceptions, and customer commitments tied to the deal.", href: `${salesOpsUrl}/production`, action: "Open Operations", icon: ReceiptText, roles: ["operations", "sales_leader", "admin"] },
  { title: "Finance", stage: "Fulfill & Get Paid", description: "Payment milestones, overdue attention, and controlled accounting handoffs.", href: `${salesOpsUrl}/orders`, action: "Open Finance", icon: BadgeDollarSign, roles: ["finance", "admin"] },
  { title: "Performance", stage: "Incentives & Performance", description: "Targets, incentives, conversion health, and board-ready reporting.", href: `${salesOpsUrl}/performance`, action: "Open Performance", icon: BarChart3, roles: ["sales_leader", "revops", "finance", "compensation_admin", "executive", "admin"] },
  { title: "Targets", stage: "Incentives & Performance", description: "Live target-versus-actual signals for teams and leaders.", href: `${salesOpsUrl}/performance`, action: "Open Targets", icon: Target, roles: ["sales_leader", "revops", "executive", "admin"] },
  { title: "Platform administration", stage: "Governance", description: "Users, roles, integrations, audit history, and approval controls.", href: "/admin", action: "Open administration", icon: UsersRound, roles: ["admin", "platform_admin"] },
]

function canOpen(card: WorkspaceCard, user: { is_superuser?: boolean; role?: string | null } | null | undefined) {
  return Boolean(user?.is_superuser || (user?.role && card.roles.includes(user.role)))
}

export default function RevenueOsHomePage() {
  const { user } = useAuth()
  const visibleWorkspaces = workspaces.filter((card) => canOpen(card, user))

  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/15 via-background to-background p-6 sm:p-8">
        <Badge variant="secondary">ARA Global</Badge>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">Revenue OS</h1>
        <p className="mt-2 text-lg text-muted-foreground">One customer record. One operating rhythm.</p>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-muted-foreground">Reach, qualify, close, fulfill, get paid, and improve performance without handing customer context from one disconnected tool to another.</p>
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Your workspaces</h2>
            <p className="mt-1 text-sm text-muted-foreground">Each workspace owns a clear stage of the revenue lifecycle. High-impact actions remain governed and auditable.</p>
          </div>
          <Badge variant="outline">{visibleWorkspaces.length} authorised areas</Badge>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleWorkspaces.map((workspace) => {
            const Icon = workspace.icon
            const external = workspace.href.startsWith("http")
            return <a className="group rounded-xl border bg-card p-5 transition-colors hover:border-primary/60 hover:bg-muted/30" href={workspace.href} key={workspace.title} rel={external ? "noreferrer" : undefined} target={external ? "_blank" : undefined}>
              <div className="flex items-start justify-between gap-4"><div className="rounded-lg bg-primary/10 p-2 text-primary"><Icon className="size-5" /></div><Badge variant="outline">{workspace.stage}</Badge></div>
              <h3 className="mt-4 text-lg font-semibold">{workspace.title}</h3>
              <p className="mt-2 min-h-12 text-sm leading-6 text-muted-foreground">{workspace.description}</p>
              <span className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-primary">{workspace.action}<ArrowUpRight className="size-4" /></span>
            </a>
          })}
        </div>
      </section>

      <section className="rounded-xl border border-dashed p-5">
        <h2 className="text-lg font-semibold">Agent workforce</h2>
        <p className="mt-1 text-sm text-muted-foreground">Capture: Outreach, Campaign & Funnel, Chat & Bot. Qualify: Lead Scoring, Pipeline, Proposal. Fulfill: Order Tracking, Payment, ERP Sync. Performance: Incentive, Target Tracking, Analytics.</p>
      </section>
    </div>
  )
}
