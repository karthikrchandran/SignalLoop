import { createFileRoute } from "@tanstack/react-router"

import AnalyticsDashboardPage from "@/features/analytics/AnalyticsDashboardPage"

export const Route = createFileRoute("/_layout/analytics")({
  component: AnalyticsDashboardPage,
  head: () => ({
    meta: [{ title: "Analytics — EngageHub" }],
  }),
})
