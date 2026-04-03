import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowRight,
  BarChart3,
  Briefcase,
  FileText,
  ListOrdered,
  Mail,
  Mic2,
  Phone,
  TrendingUp,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import useAuth from "@/hooks/useAuth"

const statCards = [
  {
    icon: Briefcase,
    label: "Active Campaigns",
    value: "—",
    trend: "across all channels",
  },
  {
    icon: Mail,
    label: "Emails Sent (Month)",
    value: "—",
    trend: "track opens & clicks in Analytics",
  },
  {
    icon: Phone,
    label: "Voice Calls (Week)",
    value: "—",
    trend: "Alex & Morgan agents",
  },
  {
    icon: TrendingUp,
    label: "Avg. Open Rate",
    value: "—",
    trend: "across email sequences",
  },
]

const featureCards = [
  {
    icon: Briefcase,
    title: "Campaigns",
    description:
      "Create multi-channel campaigns, import audiences, and schedule outreach.",
    path: "/campaigns",
  },
  {
    icon: ListOrdered,
    title: "Email Sequences",
    description:
      "Build automated drip sequences with conditional branching and A/B steps.",
    path: "/sequences",
  },
  {
    icon: Mic2,
    title: "Voice Agents",
    description:
      "Configure AI voice agents (Alex & Morgan) with custom scripts and knowledgebases.",
    path: "/voice-agents",
  },
  {
    icon: BarChart3,
    title: "Analytics",
    description:
      "Real-time dashboards for delivery rates, opens, clicks, and call outcomes.",
    path: "/analytics",
  },
  {
    icon: FileText,
    title: "Templates",
    description:
      "Manage reusable email and voice templates with live token preview.",
    path: "/templates",
  },
]

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [{ title: "Dashboard — EngageHub" }],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()
  const firstName =
    currentUser?.full_name?.split(" ")[0] || currentUser?.email?.split("@")[0] || "there"

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Welcome back, {firstName}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Here&apos;s what&apos;s happening across your campaigns and channels
          today.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map((s) => {
          const Icon = s.icon
          return (
            <Card key={s.label} className="border-border/70">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardDescription className="text-xs font-medium uppercase tracking-wide">
                  {s.label}
                </CardDescription>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{s.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{s.trend}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Feature cards */}
      <div>
        <h2 className="mb-4 text-lg font-semibold tracking-tight">
          Quick access
        </h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {featureCards.map((section) => {
            const Icon = section.icon
            return (
              <Card key={section.title} className="border-border/70">
                <CardHeader>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle>{section.title}</CardTitle>
                  <CardDescription>{section.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button asChild variant="outline" className="w-full justify-between">
                    <Link to={section.path as never}>
                      Open
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
