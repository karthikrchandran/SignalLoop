import { createFileRoute } from "@tanstack/react-router"
import KpiDashboardPage from "@/features/reporting/KpiDashboardPage"

export const Route = createFileRoute("/_layout/reporting")({
  component: KpiDashboardPage,
  head: () => ({ meta: [{ title: "KPI Dashboard — SignalLoop" }] }),
})
