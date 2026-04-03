import {
  BarChart3,
  Mail,
  MousePointerClick,
  Phone,
  TrendingUp,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useState } from "react"

const SUMMARY_STATS = [
  {
    icon: Mail,
    label: "Total Emails Sent",
    value: "24,810",
    change: "+12% vs last period",
    positive: true,
  },
  {
    icon: TrendingUp,
    label: "Avg. Open Rate",
    value: "28.4%",
    change: "+2.1 pp vs last period",
    positive: true,
  },
  {
    icon: MousePointerClick,
    label: "Avg. Click-through Rate",
    value: "6.7%",
    change: "-0.3 pp vs last period",
    positive: false,
  },
  {
    icon: Phone,
    label: "Voice Calls Completed",
    value: "1,340",
    change: "+31% vs last period",
    positive: true,
  },
]

const CAMPAIGN_RUNS = [
  {
    name: "Q2 Re-engagement Blast",
    channel: "Email",
    agent: "—",
    sent: 4200,
    opens: "31%",
    clicks: "8.2%",
    date: "2026-06-10",
    status: "Completed",
  },
  {
    name: "Product Launch Sequence",
    channel: "Email",
    agent: "—",
    sent: 8900,
    opens: "44%",
    clicks: "11%",
    date: "2026-06-04",
    status: "Completed",
  },
  {
    name: "Appointment Reminder Calls",
    channel: "Voice",
    agent: "Alex",
    sent: 560,
    opens: "—",
    clicks: "—",
    date: "2026-05-28",
    status: "Completed",
  },
  {
    name: "Win-back Follow-up",
    channel: "Voice",
    agent: "Morgan",
    sent: 780,
    opens: "—",
    clicks: "—",
    date: "2026-05-22",
    status: "Completed",
  },
  {
    name: "Welcome Onboarding Series",
    channel: "Email",
    agent: "—",
    sent: 1220,
    opens: "58%",
    clicks: "14%",
    date: "2026-05-15",
    status: "Completed",
  },
  {
    name: "Exclusive Offer Alert",
    channel: "Email",
    agent: "—",
    sent: 6100,
    opens: "22%",
    clicks: "4.1%",
    date: "2026-05-09",
    status: "Paused",
  },
  {
    name: "Survey Outreach",
    channel: "Voice",
    agent: "Morgan",
    sent: 420,
    opens: "—",
    clicks: "—",
    date: "2026-04-30",
    status: "Completed",
  },
]

const SEQUENCE_FUNNEL = [
  { step: "Enrolled", count: 8900 },
  { step: "Step 1 — Intro Email", count: 8812 },
  { step: "Step 2 — Follow-up", count: 6430 },
  { step: "Step 3 — Offer Email", count: 4100 },
  { step: "Step 4 — Final Nudge", count: 2210 },
  { step: "Converted", count: 940 },
]

export default function AnalyticsDashboardPage() {
  const [period, setPeriod] = useState("30d")

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-7 w-7 text-primary" />
            Analytics
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Performance metrics for your campaigns, email sequences, and voice
            outreach.
          </p>
        </div>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
            <SelectItem value="90d">Last 90 days</SelectItem>
            <SelectItem value="ytd">Year to date</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Summary stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {SUMMARY_STATS.map((s) => {
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
                <p
                  className={`mt-1 text-xs ${s.positive ? "text-green-600 dark:text-green-400" : "text-rose-500"}`}
                >
                  {s.change}
                </p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Campaign run history table */}
      <Card className="border-border/70">
        <CardHeader>
          <CardTitle>Past Campaign Runs</CardTitle>
          <CardDescription>
            All completed and paused campaign executions. Click a row to drill
            into contact-level delivery data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead className="text-right">Sent</TableHead>
                <TableHead className="text-right">Open Rate</TableHead>
                <TableHead className="text-right">CTR</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {CAMPAIGN_RUNS.map((run) => (
                <TableRow key={run.name} className="cursor-pointer hover:bg-muted/50">
                  <TableCell className="font-medium">{run.name}</TableCell>
                  <TableCell>{run.channel}</TableCell>
                  <TableCell>{run.agent}</TableCell>
                  <TableCell className="text-right">
                    {run.sent.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">{run.opens}</TableCell>
                  <TableCell className="text-right">{run.clicks}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {run.date}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={run.status === "Completed" ? "default" : "secondary"}
                    >
                      {run.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Sequence funnel */}
      <Card className="border-border/70">
        <CardHeader>
          <CardTitle>Email Sequence Funnel</CardTitle>
          <CardDescription>
            Contact progression through the &quot;Product Launch Sequence&quot; — most
            recent run.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {SEQUENCE_FUNNEL.map((row, i) => {
            const pct = Math.round((row.count / SEQUENCE_FUNNEL[0].count) * 100)
            return (
              <div key={row.step} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{row.step}</span>
                  <span className="text-muted-foreground">
                    {row.count.toLocaleString()} ({pct}%)
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-2 rounded-full ${i === SEQUENCE_FUNNEL.length - 1 ? "bg-green-500" : "bg-primary"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
