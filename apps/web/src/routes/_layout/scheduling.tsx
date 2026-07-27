import { createFileRoute } from "@tanstack/react-router"

import SchedulingPage from "@/features/scheduling/SchedulingPage"

export const Route = createFileRoute("/_layout/scheduling")({
  component: SchedulingPage,
  head: () => ({
    meta: [{ title: "Meetings & Scheduling — SignalLoop" }],
  }),
})
