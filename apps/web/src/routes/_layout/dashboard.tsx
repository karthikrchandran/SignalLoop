import { createFileRoute } from "@tanstack/react-router"

import SignalLoopDashboardPage from "@/features/dashboard/SignalLoopDashboardPage"

export const Route = createFileRoute("/_layout/dashboard")({
  component: SignalLoopDashboardPage,
  head: () => ({
    meta: [{ title: "Command Center - SignalLoop" }],
  }),
})
