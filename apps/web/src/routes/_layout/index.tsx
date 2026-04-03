import { createFileRoute } from "@tanstack/react-router"
import { ArrowRight, Boxes, Briefcase, FileText, Shield } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import useAuth from "@/hooks/useAuth"

const dashboardSections = [
  {
    icon: Briefcase,
    title: "Campaign intake",
    description: "Create campaigns, import audiences, and stage segments.",
    path: "/campaigns",
  },
  {
    icon: FileText,
    title: "Template library",
    description: "Manage tokenized outreach templates and publish guardrails.",
    path: "/templates",
  },
  {
    icon: Boxes,
    title: "Offer packs",
    description: "Bundle compliant template versions into reusable campaign packs.",
    path: "/offer-packs",
  },
  {
    icon: Shield,
    title: "Governance",
    description: "Apply approvals, policies, and emergency pause controls.",
    path: "/governance",
  },
]

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - FastAPI Template",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="max-w-2xl text-3xl font-semibold tracking-tight">
          {currentUser?.full_name || currentUser?.email}, manage governed outreach from one control plane.
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          EngageHub combines audience intake, reusable outreach assets, and
          governance controls for workspace-scoped campaign operations.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {dashboardSections.map((section) => {
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
                <Button asChild className="w-full justify-between">
                  <a href={section.path}>
                    Open
                    <ArrowRight className="h-4 w-4" />
                  </a>
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
